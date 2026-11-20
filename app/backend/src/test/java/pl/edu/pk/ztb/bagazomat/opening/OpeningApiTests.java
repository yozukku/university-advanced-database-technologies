package pl.edu.pk.ztb.bagazomat.opening;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.mockito.invocation.InvocationOnMock;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders;
import org.springframework.test.web.servlet.result.MockMvcResultMatchers;
import pl.edu.pk.ztb.bagazomat.PostgresContainerConfiguration;
import pl.edu.pk.ztb.bagazomat.TestRows;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

/** @author Anton Gorokh */
@SpringBootTest
@AutoConfigureMockMvc
@Import(PostgresContainerConfiguration.class)
class OpeningApiTests {

	private static final String ANNA = TestRows.ANNA.toString();
	private static final String JAN = "a4bba234-ddf1-5dbc-bf7d-fca171bfe08f";
	private static final String LOCKERMAT = "KRK-GLOWNY";
	private static final String DOOR_PENDING = "Skrytka czeka na potwierdzenie poprzedniego otwarcia.";

	private static final JsonMapper JSON = JsonMapper.builder().build();

	private static final String TRUNCATE_ORDERS = """
			truncate order_, reservation_, shipment_, payment_, access_code_, incident_, cell_opening_, audit_event_
			""";

	private static final String CODE_STATUSES = """
			select a.purpose_ || ':' || a.status_
			from access_code_ a
			         join reservation_ r on r.id_ = a.reservation_id_
			where r.order_id_ = ?
			order by a.id_
			""";

	private static final String INSERT_SHIPMENT_LEG = """
			with new_order as (insert into order_ (number_, customer_id_, type_, size_, tariff_id_, price_, payment_deadline_)
			                   select 'TEST-SHIPMENT', u.id_, 'SHIPMENT', t.size_, t.id_, t.shipment_price_, now() + interval '15 minutes'
			                   from customer_ u
			                            cross join tariff_ t
			                   where u.keycloak_id_ = ? and t.size_ = 'M'
			                   returning id_, size_)
			insert into reservation_ (order_id_, size_, cell_id_, leg_, from_, to_)
			select o.id_, o.size_, c.id_, 'ORIGIN', ?, ?
			from new_order o
			         join lockermat_cell_ c on c.size_ = o.size_ and c.number_ = 10
			         join lockermat_ l on l.id_ = c.lockermat_id_
			where l.code_ = ?
			""";

	private static final String LEG_EVENT = """
			select count(*)
			from audit_event_
			where entity_ = 'RESERVATION' and entity_id_ = ? and action_ = ?
			  and actor_ = jsonb_build_object('kind', 'CUSTOMER', 'keycloak_id', ?, 'email', 'anna@example.test')
			  and changes_ = jsonb_build_array(jsonb_build_object('f', 'status_', 'old', ?, 'new', ?))
			""";

	private final Instant now = Instant.now().truncatedTo(ChronoUnit.SECONDS);
	private final Instant from = now.minus(Duration.ofMinutes(1));
	private final Instant to = now.plus(Duration.ofHours(4));

	@MockitoSpyBean
	private SimulatedDoorGateway doorGateway;

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JdbcTemplate jdbc;

	@AfterEach
	void removeOrders() {
		jdbc.execute(TRUNCATE_ORDERS);
	}

	@Test
	void completesStorageLifeCycle() throws Exception {
		JsonNode order = book(ANNA, from, to);
		long orderId = order.path("id").asLong();
		long legId = order.path("reservationId").asLong();
		pay(ANNA, orderId);

		JsonNode dropOff = open(ANNA, legId);

		Assertions.assertEquals("DROP_OFF", dropOff.path("purpose").asString());
		Assertions.assertEquals("OPENED", dropOff.path("result").asString());
		Assertions.assertEquals("OCCUPIED", legStatus(legId));
		Assertions.assertEquals(List.of("DROP_OFF:USED", "PICK_UP:ACTIVE"), codeStatuses(orderId));
		Assertions.assertEquals("PAID", orderStatus(orderId));
		Assertions.assertEquals("PICK_UP", getOk(ANNA, "/api/orders/" + orderId + "/codes").path(0).path("purpose").asString());

		JsonNode pickUp = open(ANNA, legId);

		Assertions.assertEquals("PICK_UP", pickUp.path("purpose").asString());
		Assertions.assertEquals("OPENED", pickUp.path("result").asString());
		Assertions.assertEquals("COMPLETED", legStatus(legId));
		Assertions.assertEquals(List.of("DROP_OFF:USED", "PICK_UP:USED"), codeStatuses(orderId));
		Assertions.assertEquals(1, jdbc.queryForObject("select count(*) from order_ where id_ = ? and status_ = 'COMPLETED' and closed_at_ is not null",
				Integer.class, orderId));
		Assertions.assertEquals("COMPLETED", getOk(ANNA, "/api/orders/" + orderId).path("status").asString());
		Assertions.assertEquals(0, getOk(ANNA, "/api/orders/" + orderId + "/codes").size());
		Assertions.assertEquals(List.of("OPENED", "OPENED"), openingResults());
		Assertions.assertEquals(2, jdbc.queryForObject("""
				select count(*)
				from cell_opening_ x
				         join access_code_ a on a.id_ = x.access_code_id_
				         join reservation_ r on r.id_ = a.reservation_id_
				where x.channel_ = 'APP' and x.actor_keycloak_id_ = ?::uuid and a.used_at_ = x.requested_at_
				  and x.requested_at_ = case a.purpose_ when 'DROP_OFF' then r.deposited_at_ else r.collected_at_ end
				""", Integer.class, ANNA));

		assertError(openRequest(ANNA, legId), HttpStatus.CONFLICT);

		Assertions.assertEquals(2, countRows("cell_opening_"));
	}

	@Test
	void writesDepositAndPickUpEvents() throws Exception {
		JsonNode order = book(ANNA, from, to);
		long legId = order.path("reservationId").asLong();
		pay(ANNA, order.path("id").asLong());
		open(ANNA, legId);
		open(ANNA, legId);

		Assertions.assertEquals(List.of("ORDER:CREATED", "ORDER:PAID", "RESERVATION:DEPOSITED", "RESERVATION:COLLECTED"), auditEvents());
		Assertions.assertEquals(1, jdbc.queryForObject(LEG_EVENT, Integer.class, legId, "DEPOSITED", ANNA, "BOOKED", "OCCUPIED"));
		Assertions.assertEquals(1, jdbc.queryForObject(LEG_EVENT, Integer.class, legId, "COLLECTED", ANNA, "OCCUPIED", "COMPLETED"));
	}

	@Test
	void rejectsSecondRequestWhileCommandIsPending() throws Exception {
		long legId = bookAndPay(ANNA);
		CountDownLatch reply = new CountDownLatch(1);
		Mockito.doAnswer(invocation -> replyAfter(reply, invocation))
				.doCallRealMethod()
				.when(doorGateway)
				.open(Mockito.anyLong());

		try (ExecutorService executor = Executors.newSingleThreadExecutor()) {
			Future<MvcResult> first = executor.submit(() -> mockMvc.perform(openRequest(ANNA, legId)).andReturn());
			awaitPendingOpening();

			assertError(openRequest(ANNA, legId), HttpStatus.CONFLICT);

			reply.countDown();
			MvcResult result = first.get(30, TimeUnit.SECONDS);
			String body = result.getResponse().getContentAsString(StandardCharsets.UTF_8);
			Assertions.assertEquals(HttpStatus.OK.value(), result.getResponse().getStatus(), body);
			Assertions.assertEquals("OPENED", JSON.readTree(body).path("result").asString());
		}

		Assertions.assertEquals(List.of("OPENED"), openingResults());
		Assertions.assertEquals("OCCUPIED", legStatus(legId));
		Mockito.verify(doorGateway, Mockito.times(1)).open(Mockito.anyLong());
	}

	@Test
	void keepsCodeActiveAfterDoorFailureAndRetries() throws Exception {
		JsonNode order = book(ANNA, from, to);
		long orderId = order.path("id").asLong();
		long legId = order.path("reservationId").asLong();
		pay(ANNA, orderId);
		Mockito.doReturn(CellOpening.Result.DOOR_FAILED)
				.doCallRealMethod()
				.when(doorGateway)
				.open(Mockito.anyLong());

		JsonNode failed = open(ANNA, legId);

		Assertions.assertEquals("DROP_OFF", failed.path("purpose").asString());
		Assertions.assertEquals("DOOR_FAILED", failed.path("result").asString());
		Assertions.assertEquals(List.of("DOOR_FAILED"), openingResults());
		Assertions.assertEquals(List.of("DROP_OFF:ACTIVE", "PICK_UP:ACTIVE"), codeStatuses(orderId));
		Assertions.assertEquals("BOOKED", legStatus(legId));
		Assertions.assertEquals(List.of("ORDER:CREATED", "ORDER:PAID"), auditEvents());

		JsonNode retried = open(ANNA, legId);

		Assertions.assertEquals("DROP_OFF", retried.path("purpose").asString());
		Assertions.assertEquals("OPENED", retried.path("result").asString());
		Assertions.assertEquals(List.of("DOOR_FAILED", "OPENED"), openingResults());
		Assertions.assertEquals(1, jdbc.queryForObject("select count(distinct access_code_id_) from cell_opening_", Integer.class));
		Assertions.assertEquals(List.of("DROP_OFF:USED", "PICK_UP:ACTIVE"), codeStatuses(orderId));
		Assertions.assertEquals("OCCUPIED", legStatus(legId));
	}

	@Test
	void leavesCommandPendingAfterLostReply() throws Exception {
		JsonNode order = book(ANNA, from, to);
		long orderId = order.path("id").asLong();
		long legId = order.path("reservationId").asLong();
		pay(ANNA, orderId);
		Mockito.doReturn(CellOpening.Result.PENDING)
				.when(doorGateway)
				.open(Mockito.anyLong());

		JsonNode lost = open(ANNA, legId);

		Assertions.assertEquals("PENDING", lost.path("result").asString());
		Assertions.assertEquals(DOOR_PENDING, assertError(openRequest(ANNA, legId), HttpStatus.CONFLICT).path("message").asString());
		assertError(post(ANNA, "/api/orders/" + orderId + "/cancel"), HttpStatus.CONFLICT);

		Assertions.assertEquals(List.of("PENDING"), openingResults());
		Assertions.assertEquals(List.of("DROP_OFF:ACTIVE", "PICK_UP:ACTIVE"), codeStatuses(orderId));
		Assertions.assertEquals("BOOKED", legStatus(legId));
		Assertions.assertEquals("PAID", orderStatus(orderId));
		Mockito.verify(doorGateway, Mockito.times(1)).open(Mockito.anyLong());
	}

	@Test
	void hidesLegOfOtherCustomer() throws Exception {
		long legId = bookAndPay(ANNA);
		jdbc.update(INSERT_SHIPMENT_LEG, TestRows.ANNA, from.atOffset(ZoneOffset.UTC), to.atOffset(ZoneOffset.UTC), LOCKERMAT);
		long shipmentLegId = jdbc.queryForObject("select id_ from reservation_ where leg_ = 'ORIGIN'", Long.class);

		assertError(openRequest(JAN, legId), HttpStatus.NOT_FOUND);
		assertError(openRequest(ANNA, shipmentLegId), HttpStatus.NOT_FOUND);
		assertError(openRequest(ANNA, shipmentLegId + 1), HttpStatus.NOT_FOUND);

		Assertions.assertEquals(0, countRows("cell_opening_"));
		Assertions.assertEquals("BOOKED", legStatus(legId));
		Mockito.verify(doorGateway, Mockito.never()).open(Mockito.anyLong());
	}

	@Test
	void rejectsLegThatCannotBeOpenedNow() throws Exception {
		long unpaidLegId = book(ANNA, from, to).path("reservationId").asLong();
		Instant tomorrow = now.plus(Duration.ofDays(1));
		long futureLegId = bookAndPay(ANNA, tomorrow, tomorrow.plus(Duration.ofHours(4)));
		Instant later = now.plus(Duration.ofDays(2));
		JsonNode cancelled = book(ANNA, later, later.plus(Duration.ofHours(4)));
		perform(post(ANNA, "/api/orders/" + cancelled.path("id").asLong() + "/cancel"), HttpStatus.OK);

		assertError(openRequest(ANNA, unpaidLegId), HttpStatus.CONFLICT);
		assertError(openRequest(ANNA, futureLegId), HttpStatus.CONFLICT);
		assertError(openRequest(ANNA, cancelled.path("reservationId").asLong()), HttpStatus.CONFLICT);

		Assertions.assertEquals(0, countRows("cell_opening_"));
		Mockito.verify(doorGateway, Mockito.never()).open(Mockito.anyLong());
	}

	private Object replyAfter(CountDownLatch reply, InvocationOnMock invocation) throws Throwable {
		Assertions.assertTrue(reply.await(10, TimeUnit.SECONDS), "Bramka nie dostała zgody na odpowiedź");
		return invocation.callRealMethod();
	}

	private void awaitPendingOpening() throws InterruptedException {
		Instant limit = Instant.now().plus(Duration.ofSeconds(10));
		while (jdbc.queryForObject("select count(*) from cell_opening_ where result_ = 'PENDING'", Integer.class) == 0) {
			Assertions.assertTrue(Instant.now().isBefore(limit), "Polecenie PENDING nie jest zatwierdzone przed wysłaniem do bramki");
			Thread.sleep(20);
		}
	}

	private long bookAndPay(String subject) throws Exception {
		return bookAndPay(subject, from, to);
	}

	private long bookAndPay(String subject, Instant windowFrom, Instant windowTo) throws Exception {
		JsonNode order = book(subject, windowFrom, windowTo);
		pay(subject, order.path("id").asLong());
		return order.path("reservationId").asLong();
	}

	private JsonNode book(String subject, Instant windowFrom, Instant windowTo) throws Exception {
		Map<String, Object> order = Map.of("lockermatId", lockermatId(), "size", "S", "from", windowFrom.toString(), "to", windowTo.toString());
		MockHttpServletRequestBuilder request = post(subject, "/api/orders")
				.contentType(MediaType.APPLICATION_JSON)
				.content(JSON.writeValueAsString(order));
		return JSON.readTree(perform(request, HttpStatus.CREATED));
	}

	private void pay(String subject, long orderId) throws Exception {
		MockHttpServletRequestBuilder request = post(subject, "/api/orders/" + orderId + "/payments")
				.contentType(MediaType.APPLICATION_JSON)
				.content(JSON.writeValueAsString(Map.of("result", "SUCCESS")));
		perform(request, HttpStatus.CREATED);
	}

	private JsonNode open(String subject, long reservationId) throws Exception {
		return JSON.readTree(perform(openRequest(subject, reservationId), HttpStatus.OK));
	}

	private MockHttpServletRequestBuilder openRequest(String subject, long reservationId) {
		return post(subject, "/api/reservations/" + reservationId + "/open");
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

	private JsonNode assertError(MockHttpServletRequestBuilder request, HttpStatus status) throws Exception {
		MvcResult result = mockMvc.perform(request).andReturn();
		String body = result.getResponse().getContentAsString(StandardCharsets.UTF_8);
		Assertions.assertEquals(status.value(), result.getResponse().getStatus(), body);
		JsonNode error = JSON.readTree(body);
		Assertions.assertEquals(status.name(), error.path("code").asString(), body);
		Assertions.assertFalse(error.path("message").asString().isBlank(), body);
		return error;
	}

	private List<String> codeStatuses(long orderId) {
		return jdbc.queryForList(CODE_STATUSES, String.class, orderId);
	}

	private List<String> openingResults() {
		return jdbc.queryForList("select result_ from cell_opening_ order by id_", String.class);
	}

	private List<String> auditEvents() {
		return jdbc.queryForList("select entity_ || ':' || action_ from audit_event_ order by id_", String.class);
	}

	private String legStatus(long legId) {
		return jdbc.queryForObject("select status_ from reservation_ where id_ = ?", String.class, legId);
	}

	private String orderStatus(long orderId) {
		return jdbc.queryForObject("select status_ from order_ where id_ = ?", String.class, orderId);
	}

	private int countRows(String table) {
		return jdbc.queryForObject("select count(*) from " + table, Integer.class);
	}

	private long lockermatId() {
		return jdbc.queryForObject("select id_ from lockermat_ where code_ = ?", Long.class, LOCKERMAT);
	}
}
