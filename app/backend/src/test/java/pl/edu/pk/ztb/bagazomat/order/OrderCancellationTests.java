package pl.edu.pk.ztb.bagazomat.order;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
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
import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;

/** @author Anton Gorokh */
@SpringBootTest
@AutoConfigureMockMvc
@Import(PostgresContainerConfiguration.class)
class OrderCancellationTests {

	private static final String ANNA = TestRows.ANNA.toString();
	private static final String JAN = "a4bba234-ddf1-5dbc-bf7d-fca171bfe08f";
	private static final String LOCKERMAT = "KRK-GLOWNY";

	private static final JsonMapper JSON = JsonMapper.builder()
			.enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS)
			.build();

	private static final String TRUNCATE_ORDERS = """
			truncate order_, reservation_, shipment_, payment_, access_code_, incident_, cell_opening_, audit_event_
			""";

	private static final String CODE_STATUSES = """
			select a.status_
			from access_code_ a
			         join reservation_ r on r.id_ = a.reservation_id_
			where r.order_id_ = ?
			order by a.id_
			""";

	private final Instant from = Instant.now().plus(Duration.ofDays(1)).truncatedTo(ChronoUnit.SECONDS);
	private final Instant to = from.plus(Duration.ofHours(25));

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JdbcTemplate jdbc;

	@AfterEach
	void removeOrders() {
		jdbc.execute(TRUNCATE_ORDERS);
	}

	@Test
	void cancelsPaidOrderWithFullRefund() throws Exception {
		JsonNode order = book(ANNA, from, to);
		long id = order.path("id").asLong();
		long chargeId = pay(ANNA, id);

		JsonNode cancelled = cancel(ANNA, id);

		Assertions.assertEquals(id, cancelled.path("id").asLong());
		Assertions.assertEquals("CANCELLED", cancelled.path("status").asString());
		Assertions.assertEquals(new BigDecimal("30.00"), cancelled.path("refund").decimalValue());
		Assertions.assertEquals(1, jdbc.queryForObject("select count(*) from order_ where id_ = ? and status_ = 'CANCELLED' and closed_at_ is not null",
				Integer.class, id));
		Assertions.assertEquals(List.of("CANCELLED"), jdbc.queryForList("select status_ from reservation_ where order_id_ = ?", String.class, id));
		Assertions.assertEquals(List.of("REVOKED", "REVOKED"), jdbc.queryForList(CODE_STATUSES, String.class, id));
		Assertions.assertEquals(0, getOk(ANNA, "/api/orders/" + id + "/codes").size());
		Assertions.assertEquals(1, jdbc.queryForObject("""
				select count(*)
				from payment_ r
				         join order_ o on o.id_ = r.order_id_
				where r.kind_ = 'REFUND' and r.refund_of_id_ = ? and r.amount_ = o.price_ and r.status_ = 'COMPLETED'
				  and r.provider_ = 'MOCK' and r.provider_ref_ = 'MOCK-' || lpad(r.id_::text, 10, '0') and r.completed_at_ is not null
				""", Integer.class, chargeId));
		Assertions.assertEquals(order.path("cellNumber").asInt(), book(ANNA, from, to).path("cellNumber").asInt());
	}

	@Test
	void cancelsUnpaidOrderWithoutRefund() throws Exception {
		long id = book(ANNA, from, to).path("id").asLong();

		JsonNode cancelled = cancel(ANNA, id);

		Assertions.assertEquals(new BigDecimal("0.00"), cancelled.path("refund").decimalValue());
		Assertions.assertEquals("CANCELLED", orderStatus(id));
		Assertions.assertEquals(List.of("CANCELLED"), jdbc.queryForList("select status_ from reservation_ where order_id_ = ?", String.class, id));
		Assertions.assertEquals(0, countRows("payment_"));
		Assertions.assertEquals(1, jdbc.queryForObject("""
				select count(*)
				from audit_event_
				where entity_ = 'ORDER' and entity_id_ = ? and action_ = 'CANCELLED'
				  and changes_ = '[{"f": "status_", "old": "AWAITING_PAYMENT", "new": "CANCELLED"}]'::jsonb
				""", Integer.class, id));
	}

	@Test
	void rejectsSecondCancel() throws Exception {
		long paidId = book(ANNA, from, to).path("id").asLong();
		pay(ANNA, paidId);
		cancel(ANNA, paidId);
		long unpaidId = book(ANNA, from, to).path("id").asLong();
		cancel(ANNA, unpaidId);

		assertError(cancelRequest(ANNA, paidId), HttpStatus.CONFLICT);
		assertError(cancelRequest(ANNA, unpaidId), HttpStatus.CONFLICT);

		Assertions.assertEquals(1, jdbc.queryForObject("select count(*) from payment_ where kind_ = 'REFUND'", Integer.class));
		Assertions.assertEquals(List.of("CREATED", "PAID", "CANCELLED", "REFUNDED", "CREATED", "CANCELLED"), auditActions());
	}

	@Test
	void refusesCancelAfterDeposit() throws Exception {
		Instant now = Instant.now().truncatedTo(ChronoUnit.SECONDS);
		long id = book(ANNA, now.minus(Duration.ofHours(1)), now.plus(Duration.ofHours(4))).path("id").asLong();
		pay(ANNA, id);
		jdbc.update("update reservation_ set status_ = 'OCCUPIED', deposited_at_ = now() where order_id_ = ?", id);
		jdbc.update("""
				update access_code_ a set status_ = 'USED', used_at_ = now()
				from reservation_ r
				where r.id_ = a.reservation_id_ and r.order_id_ = ? and a.purpose_ = 'DROP_OFF'
				""", id);

		assertError(cancelRequest(ANNA, id), HttpStatus.CONFLICT);

		Assertions.assertEquals("PAID", orderStatus(id));
		Assertions.assertEquals(List.of("OCCUPIED"), jdbc.queryForList("select status_ from reservation_ where order_id_ = ?", String.class, id));
		Assertions.assertEquals(List.of("USED", "ACTIVE"), jdbc.queryForList(CODE_STATUSES, String.class, id));
		Assertions.assertEquals(1, countRows("payment_"));
		Assertions.assertEquals(List.of("CREATED", "PAID"), auditActions());
	}

	@Test
	void refusesCancelWhileDoorCommandIsPending() throws Exception {
		long id = book(ANNA, from, to).path("id").asLong();
		pay(ANNA, id);
		jdbc.update("""
				insert into cell_opening_ (access_code_id_, channel_, actor_keycloak_id_, result_)
				select a.id_, 'APP', ?::uuid, 'PENDING'
				from access_code_ a
				         join reservation_ r on r.id_ = a.reservation_id_
				where r.order_id_ = ? and a.purpose_ = 'DROP_OFF'
				""", ANNA, id);

		assertError(cancelRequest(ANNA, id), HttpStatus.CONFLICT);

		Assertions.assertEquals("PAID", orderStatus(id));
		Assertions.assertEquals(List.of("BOOKED"), jdbc.queryForList("select status_ from reservation_ where order_id_ = ?", String.class, id));
		Assertions.assertEquals(List.of("ACTIVE", "ACTIVE"), jdbc.queryForList(CODE_STATUSES, String.class, id));
		Assertions.assertEquals(1, countRows("payment_"));

		jdbc.update("update cell_opening_ set result_ = 'DOOR_FAILED' where result_ = 'PENDING'");

		Assertions.assertEquals("CANCELLED", cancel(ANNA, id).path("status").asString());
	}

	@Test
	void writesCancelAndRefundEvents() throws Exception {
		long id = book(ANNA, from, to).path("id").asLong();
		pay(ANNA, id);
		cancel(ANNA, id);
		long refundId = jdbc.queryForObject("select id_ from payment_ where kind_ = 'REFUND'", Long.class);

		Assertions.assertEquals(List.of("CREATED", "PAID", "CANCELLED", "REFUNDED"), auditActions());
		Assertions.assertEquals(1, jdbc.queryForObject("""
				select count(*)
				from audit_event_
				where entity_ = 'ORDER' and entity_id_ = ? and action_ = 'CANCELLED'
				  and actor_ = jsonb_build_object('kind', 'CUSTOMER', 'keycloak_id', ?, 'email', 'anna@example.test')
				  and changes_ = '[{"f": "status_", "old": "PAID", "new": "CANCELLED"}]'::jsonb
				""", Integer.class, id, ANNA));
		Assertions.assertEquals(1, jdbc.queryForObject("""
				select count(*)
				from audit_event_
				where entity_ = 'PAYMENT' and entity_id_ = ? and action_ = 'REFUNDED'
				  and actor_ = jsonb_build_object('kind', 'CUSTOMER', 'keycloak_id', ?, 'email', 'anna@example.test')
				  and changes_ = '[{"f": "status_", "old": null, "new": "COMPLETED"}]'::jsonb
				""", Integer.class, refundId, ANNA));
	}

	@Test
	void hidesOrderOfOtherCustomer() throws Exception {
		long id = book(ANNA, from, to).path("id").asLong();
		pay(ANNA, id);

		assertError(cancelRequest(JAN, id), HttpStatus.NOT_FOUND);
		assertError(cancelRequest(ANNA, id + 1), HttpStatus.NOT_FOUND);

		Assertions.assertEquals("PAID", orderStatus(id));
		Assertions.assertEquals(1, countRows("payment_"));
	}

	private JsonNode book(String subject, Instant windowFrom, Instant windowTo) throws Exception {
		Map<String, Object> order = Map.of("lockermatId", lockermatId(), "size", "S", "from", windowFrom.toString(), "to", windowTo.toString());
		MockHttpServletRequestBuilder request = post(subject, "/api/orders")
				.contentType(MediaType.APPLICATION_JSON)
				.content(JSON.writeValueAsString(order));
		return JSON.readTree(perform(request, HttpStatus.CREATED));
	}

	private long pay(String subject, long orderId) throws Exception {
		MockHttpServletRequestBuilder request = post(subject, "/api/orders/" + orderId + "/payments")
				.contentType(MediaType.APPLICATION_JSON)
				.content(JSON.writeValueAsString(Map.of("result", "SUCCESS")));
		return JSON.readTree(perform(request, HttpStatus.CREATED)).path("id").asLong();
	}

	private JsonNode cancel(String subject, long orderId) throws Exception {
		return JSON.readTree(perform(cancelRequest(subject, orderId), HttpStatus.OK));
	}

	private MockHttpServletRequestBuilder cancelRequest(String subject, long orderId) {
		return post(subject, "/api/orders/" + orderId + "/cancel");
	}

	private JsonNode getOk(String subject, String path) throws Exception {
		return JSON.readTree(perform(as(subject, MockMvcRequestBuilders.get(path)), HttpStatus.OK));
	}

	private MockHttpServletRequestBuilder post(String subject, String path) {
		return as(subject, MockMvcRequestBuilders.post(path)).with(SecurityMockMvcRequestPostProcessors.csrf());
	}

	private MockHttpServletRequestBuilder as(String subject, MockHttpServletRequestBuilder request) {
		String email = subject.equals(ANNA) ? "anna@example.test" : "jan@example.test";
		return request.with(SecurityMockMvcRequestPostProcessors.jwt().jwt(jwt -> jwt.subject(subject).claim("email", email)));
	}

	private String perform(MockHttpServletRequestBuilder request, HttpStatus status) throws Exception {
		return mockMvc.perform(request)
				.andExpect(MockMvcResultMatchers.status().is(status.value()))
				.andReturn()
				.getResponse()
				.getContentAsString(StandardCharsets.UTF_8);
	}

	private void assertError(MockHttpServletRequestBuilder request, HttpStatus status) throws Exception {
		MvcResult result = mockMvc.perform(request).andReturn();
		String body = result.getResponse().getContentAsString(StandardCharsets.UTF_8);
		Assertions.assertEquals(status.value(), result.getResponse().getStatus(), body);
		JsonNode error = JSON.readTree(body);
		Assertions.assertEquals(status.name(), error.path("code").asString(), body);
		Assertions.assertFalse(error.path("message").asString().isBlank(), body);
	}

	private List<String> auditActions() {
		return jdbc.queryForList("select action_ from audit_event_ order by id_", String.class);
	}

	private String orderStatus(long id) {
		return jdbc.queryForObject("select status_ from order_ where id_ = ?", String.class, id);
	}

	private int countRows(String table) {
		return jdbc.queryForObject("select count(*) from " + table, Integer.class);
	}

	private long lockermatId() {
		return jdbc.queryForObject("select id_ from lockermat_ where code_ = ?", Long.class, LOCKERMAT);
	}
}
