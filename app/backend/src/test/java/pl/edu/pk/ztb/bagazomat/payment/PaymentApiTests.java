package pl.edu.pk.ztb.bagazomat.payment;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders;
import org.springframework.test.web.servlet.result.MockMvcResultMatchers;
import pl.edu.pk.ztb.bagazomat.PostgresContainerConfiguration;
import pl.edu.pk.ztb.bagazomat.TestRows;
import pl.edu.pk.ztb.bagazomat.access.AccessCodeHmac;
import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.time.Duration;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import javax.sql.DataSource;

/** @author Anton Gorokh */
@SpringBootTest
@AutoConfigureMockMvc
@Import(PostgresContainerConfiguration.class)
class PaymentApiTests {

	private static final String ANNA = TestRows.ANNA.toString();
	private static final String JAN = "a4bba234-ddf1-5dbc-bf7d-fca171bfe08f";
	private static final String LOCKERMAT = "KRK-GLOWNY";
	private static final String SUCCESS = "SUCCESS";
	private static final String FAILURE = "FAILURE";

	private static final JsonMapper JSON = JsonMapper.builder()
			.enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS)
			.build();

	private static final String TRUNCATE_ORDERS = """
			truncate order_, reservation_, shipment_, payment_, access_code_, incident_, cell_opening_, audit_event_
			""";

	private static final String INSERT_FIXTURE_CODE = """
			insert into access_code_ (id_, reservation_id_, purpose_, code_hmac_, valid_from_, valid_to_)
			select ?, r.id_, 'DROP_OFF', ?, r.from_, r.to_
			from reservation_ r
			where r.order_id_ = ?
			""";

	private static final String ORDER_CODES = """
			select a.id_
			from access_code_ a
			         join reservation_ r on r.id_ = a.reservation_id_
			where r.order_id_ = ?
			order by a.id_
			""";

	private final Instant from = Instant.now().plus(Duration.ofDays(1)).truncatedTo(ChronoUnit.SECONDS);
	private final Instant to = from.plus(Duration.ofHours(4));

	@Value("${bagazomat.access.pin-secret}")
	private String pinSecret;

	@Value("${bagazomat.access.code-secret}")
	private String codeSecret;

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JdbcTemplate jdbc;

	@Autowired
	private DataSource dataSource;

	@Autowired
	private AccessCodeHmac accessCodeHmac;

	@AfterEach
	void removeOrders() {
		jdbc.execute(TRUNCATE_ORDERS);
	}

	@Test
	void issuesOneCodePerPurposeAfterFailedAndSuccessfulPayment() throws Exception {
		long id = book(ANNA, from, to);

		JsonNode failed = pay(ANNA, id, FAILURE);
		JsonNode paid = pay(ANNA, id, SUCCESS);

		Assertions.assertEquals("FAILED", failed.path("status").asString());
		Assertions.assertEquals("COMPLETED", paid.path("status").asString());
		Assertions.assertEquals(new BigDecimal("15.00"), paid.path("amount").decimalValue());
		Assertions.assertEquals(List.of("FAILED", "COMPLETED"),
				jdbc.queryForList("select status_ from payment_ where order_id_ = ? and kind_ = 'CHARGE' and provider_ = 'MOCK' order by id_", String.class, id));
		Assertions.assertEquals("MOCK-%010d".formatted(paid.path("id").asLong()),
				jdbc.queryForObject("select provider_ref_ from payment_ where id_ = ?", String.class, paid.path("id").asLong()));
		Assertions.assertEquals("PAID", orderStatus(id));
		Assertions.assertEquals(List.of("DROP_OFF", "PICK_UP"), jdbc.queryForList("""
				select a.purpose_
				from access_code_ a
				         join reservation_ r on r.id_ = a.reservation_id_
				where r.order_id_ = ? and a.status_ = 'ACTIVE' and a.valid_from_ = r.from_ and a.valid_to_ = r.to_
				order by a.purpose_
				""", String.class, id));
	}

	@Test
	void paysOrderOnlyOnce() throws Exception {
		long id = book(ANNA, from, to);
		pay(ANNA, id, SUCCESS);

		assertError(payRequest(ANNA, id, SUCCESS), HttpStatus.CONFLICT, "CONFLICT");
		assertError(payRequest(ANNA, id, FAILURE), HttpStatus.CONFLICT, "CONFLICT");

		Assertions.assertEquals(1, countRows("payment_"));
		Assertions.assertEquals(2, countRows("access_code_"));
	}

	@Test
	void refusesPaymentWhenDeadlinePassesWhileWaitingForLock() throws Exception {
		Instant end = Instant.now().plus(Duration.ofSeconds(3));
		long id = book(ANNA, end.minus(Duration.ofHours(1)), end);
		Instant deadline = jdbc.queryForObject("select payment_deadline_ from order_ where id_ = ?", OffsetDateTime.class, id).toInstant();

		MvcResult result = payWhileLockedUntil(id, deadline.plus(Duration.ofSeconds(1)));

		assertError(result, HttpStatus.CONFLICT, "CONFLICT");
		Assertions.assertEquals(0, countRows("payment_"));
		Assertions.assertEquals(0, countRows("access_code_"));
		Assertions.assertEquals("AWAITING_PAYMENT", orderStatus(id));
	}

	@Test
	void retriesPaymentAfterForcedHmacCollision() throws Exception {
		long janOrder = book(JAN, from, to);
		long annaOrder = book(ANNA, from, to);
		long fixtureId = jdbc.queryForObject("select nextval('access_code_id_seq_')", Long.class);
		long collidingId = fixtureId + 1;
		jdbc.update(INSERT_FIXTURE_CODE, fixtureId, accessCodeHmac.codeHmacOf(accessCodeHmac.pinOf(collidingId)), janOrder);

		JsonNode payment = pay(ANNA, annaOrder, SUCCESS);

		Assertions.assertEquals("COMPLETED", payment.path("status").asString());
		Assertions.assertEquals(List.of("COMPLETED"), jdbc.queryForList("select status_ from payment_ where order_id_ = ?", String.class, annaOrder));
		Assertions.assertEquals(List.of(collidingId + 1, collidingId + 2), jdbc.queryForList(ORDER_CODES, Long.class, annaOrder));
		Assertions.assertEquals(1, countRows("payment_"));
	}

	@Test
	void doesNotRetryOtherExclusionViolation() throws Exception {
		long id = book(ANNA, from, to);
		byte[] digest = new byte[32];
		new SecureRandom().nextBytes(digest);
		jdbc.update(INSERT_FIXTURE_CODE, jdbc.queryForObject("select nextval('access_code_id_seq_')", Long.class), digest, id);
		long lastCodeId = lastValue("access_code_id_seq_");

		assertError(payRequest(ANNA, id, SUCCESS), HttpStatus.CONFLICT, "CONFLICT");

		Assertions.assertEquals(lastCodeId + 1, lastValue("access_code_id_seq_"));
		Assertions.assertEquals(0, countRows("payment_"));
		Assertions.assertEquals("AWAITING_PAYMENT", orderStatus(id));
	}

	@Test
	void redisplaysSamePinAfterRestart() throws Exception {
		long id = book(ANNA, from, to);
		pay(ANNA, id, SUCCESS);
		AccessCodeHmac restarted = new AccessCodeHmac(pinSecret, codeSecret);

		JsonNode codes = getOk(ANNA, "/api/orders/" + id + "/codes");
		List<Map<String, Object>> rows = jdbc.queryForList("""
				select a.id_, a.code_hmac_
				from access_code_ a
				         join reservation_ r on r.id_ = a.reservation_id_
				where r.order_id_ = ?
				order by a.id_
				""", id);

		Assertions.assertEquals(codes, getOk(ANNA, "/api/orders/" + id + "/codes"));
		Assertions.assertEquals(2, codes.size());
		Assertions.assertEquals("DROP_OFF", codes.get(0).path("purpose").asString());
		Assertions.assertEquals("PICK_UP", codes.get(1).path("purpose").asString());
		for (int index = 0; index < rows.size(); index++) {
			String pin = codes.get(index).path("pin").asString();
			Assertions.assertTrue(pin.matches("[0-9]{6}"), pin);
			Assertions.assertEquals(restarted.pinOf((Long) rows.get(index).get("id_")), pin);
			Assertions.assertArrayEquals(restarted.codeHmacOf(pin), (byte[]) rows.get(index).get("code_hmac_"));
			Assertions.assertEquals(from, Instant.parse(codes.get(index).path("validFrom").asString()));
			Assertions.assertEquals(to, Instant.parse(codes.get(index).path("validTo").asString()));
		}
	}

	@Test
	void writesPaidEventOnlyForSuccessfulPayment() throws Exception {
		long id = book(ANNA, from, to);
		pay(ANNA, id, FAILURE);
		pay(ANNA, id, SUCCESS);

		Assertions.assertEquals(1, jdbc.queryForObject("""
				select count(*)
				from audit_event_
				where entity_ = 'ORDER' and entity_id_ = ? and action_ = 'PAID'
				  and actor_ = jsonb_build_object('kind', 'CUSTOMER', 'keycloak_id', ?, 'email', 'anna@example.test')
				  and changes_ = '[{"f": "status_", "old": "AWAITING_PAYMENT", "new": "PAID"}]'::jsonb
				""", Integer.class, id, ANNA));
		Assertions.assertEquals(List.of("CREATED", "PAID"), jdbc.queryForList("select action_ from audit_event_ order by id_", String.class));
	}

	@Test
	void hidesOrderOfOtherCustomer() throws Exception {
		long id = book(ANNA, from, to);

		Assertions.assertEquals(0, getOk(ANNA, "/api/orders/" + id + "/codes").size());
		assertError(payRequest(JAN, id, SUCCESS), HttpStatus.NOT_FOUND, "NOT_FOUND");
		pay(ANNA, id, SUCCESS);
		assertError(get(JAN, "/api/orders/" + id + "/codes"), HttpStatus.NOT_FOUND, "NOT_FOUND");
		assertError(payRequest(ANNA, id + 1, SUCCESS), HttpStatus.NOT_FOUND, "NOT_FOUND");

		Assertions.assertEquals(1, countRows("payment_"));
	}

	@Test
	void rejectsMissingOrUnknownResult() throws Exception {
		long id = book(ANNA, from, to);

		assertError(payRequest(ANNA, id, Map.of()), HttpStatus.BAD_REQUEST, "BAD_REQUEST");
		assertError(payRequest(ANNA, id, Map.of("result", "MAYBE")), HttpStatus.BAD_REQUEST, "BAD_REQUEST");

		Assertions.assertEquals(0, countRows("payment_"));
	}

	private MvcResult payWhileLockedUntil(long orderId, Instant release) throws Exception {
		try (ExecutorService executor = Executors.newSingleThreadExecutor(); Connection holder = dataSource.getConnection()) {
			holder.setAutoCommit(false);
			try (PreparedStatement lock = holder.prepareStatement("select id_ from order_ where id_ = ? for update")) {
				lock.setLong(1, orderId);
				lock.executeQuery().close();
			}
			Future<MvcResult> payment = executor.submit(() -> mockMvc.perform(payRequest(ANNA, orderId, SUCCESS)).andReturn());
			awaitLockWait();
			Assertions.assertTrue(Instant.now().isBefore(release.minus(Duration.ofSeconds(1))));
			Thread.sleep(Math.max(0, Duration.between(Instant.now(), release).toMillis()));
			holder.commit();
			return payment.get(30, TimeUnit.SECONDS);
		}
	}

	private void awaitLockWait() throws InterruptedException {
		Instant limit = Instant.now().plus(Duration.ofSeconds(10));
		while (jdbc.queryForObject("select count(*) from pg_locks where not granted", Integer.class) == 0) {
			Assertions.assertTrue(Instant.now().isBefore(limit), "Płatność nie czeka na blokadę zamówienia");
			Thread.sleep(20);
		}
	}

	private long book(String subject, Instant windowFrom, Instant windowTo) throws Exception {
		Map<String, Object> order = Map.of("lockermatId", lockermatId(), "size", "S", "from", windowFrom.toString(), "to", windowTo.toString());
		MockHttpServletRequestBuilder request = as(subject, MockMvcRequestBuilders.post("/api/orders"))
				.with(SecurityMockMvcRequestPostProcessors.csrf())
				.contentType(MediaType.APPLICATION_JSON)
				.content(JSON.writeValueAsString(order));
		return JSON.readTree(perform(request, HttpStatus.CREATED)).path("id").asLong();
	}

	private JsonNode pay(String subject, long orderId, String result) throws Exception {
		return JSON.readTree(perform(payRequest(subject, orderId, result), HttpStatus.CREATED));
	}

	private MockHttpServletRequestBuilder payRequest(String subject, long orderId, String result) {
		return payRequest(subject, orderId, Map.of("result", result));
	}

	private MockHttpServletRequestBuilder payRequest(String subject, long orderId, Map<String, Object> body) {
		return as(subject, MockMvcRequestBuilders.post("/api/orders/" + orderId + "/payments"))
				.with(SecurityMockMvcRequestPostProcessors.csrf())
				.contentType(MediaType.APPLICATION_JSON)
				.content(JSON.writeValueAsString(body));
	}

	private MockHttpServletRequestBuilder get(String subject, String path) {
		return as(subject, MockMvcRequestBuilders.get(path));
	}

	private JsonNode getOk(String subject, String path) throws Exception {
		return JSON.readTree(perform(get(subject, path), HttpStatus.OK));
	}

	private String perform(MockHttpServletRequestBuilder request, HttpStatus status) throws Exception {
		return mockMvc.perform(request)
				.andExpect(MockMvcResultMatchers.status().is(status.value()))
				.andReturn()
				.getResponse()
				.getContentAsString(StandardCharsets.UTF_8);
	}

	private MockHttpServletRequestBuilder as(String subject, MockHttpServletRequestBuilder request) {
		String email = subject.equals(ANNA) ? "anna@example.test" : "jan@example.test";
		return request.with(SecurityMockMvcRequestPostProcessors.jwt().jwt(jwt -> jwt.subject(subject).claim("email", email)));
	}

	private void assertError(MockHttpServletRequestBuilder request, HttpStatus status, String code) throws Exception {
		assertError(mockMvc.perform(request).andReturn(), status, code);
	}

	private void assertError(MvcResult result, HttpStatus status, String code) throws Exception {
		String body = result.getResponse().getContentAsString(StandardCharsets.UTF_8);
		Assertions.assertEquals(status.value(), result.getResponse().getStatus(), body);
		JsonNode error = JSON.readTree(body);
		Assertions.assertEquals(code, error.path("code").asString(), body);
		Assertions.assertFalse(error.path("message").asString().isBlank(), body);
	}

	private String orderStatus(long id) {
		return jdbc.queryForObject("select status_ from order_ where id_ = ?", String.class, id);
	}

	private long lastValue(String sequence) {
		return jdbc.queryForObject("select last_value from " + sequence, Long.class);
	}

	private int countRows(String table) {
		return jdbc.queryForObject("select count(*) from " + table, Integer.class);
	}

	private long lockermatId() {
		return jdbc.queryForObject("select id_ from lockermat_ where code_ = ?", Long.class, LOCKERMAT);
	}
}
