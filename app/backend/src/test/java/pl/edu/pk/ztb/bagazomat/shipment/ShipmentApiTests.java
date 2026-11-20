package pl.edu.pk.ztb.bagazomat.shipment;

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
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders;
import pl.edu.pk.ztb.bagazomat.PostgresContainerConfiguration;
import pl.edu.pk.ztb.bagazomat.TestRows;
import pl.edu.pk.ztb.bagazomat.access.AccessCodeHmac;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** @author Anton Gorokh */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("dev")
@Import(PostgresContainerConfiguration.class)
class ShipmentApiTests {

	private static final String ANNA = TestRows.ANNA.toString();
	private static final String JAN = "a4bba234-ddf1-5dbc-bf7d-fca171bfe08f";
	private static final String JAN_PHONE = "+48500100300";
	private static final String DEMO_SENDER = "95912bb7-ca81-5398-b494-078466a4edd2";
	private static final String LOCKERMAT = "KRK-GLOWNY";
	private static final Map<String, List<String>> USERS = Map.of(
			ANNA, List.of("anna@example.test", "Anna Kowalska"),
			JAN, List.of("jan@example.test", "Jan Nowak"));

	private static final JsonMapper JSON = JsonMapper.builder().build();

	private static final String TRUNCATE_ORDERS = """
			truncate order_, reservation_, shipment_, payment_, access_code_, incident_, cell_opening_, audit_event_
			""";

	private static final String SHARED_HMACS_IN_OVERLAPPING_WINDOWS = """
			select count(*)
			from access_code_ a
			         join access_code_ b on b.id_ > a.id_ and b.code_hmac_ = a.code_hmac_
			where tstzrange(a.valid_from_, a.valid_to_, '[)') && tstzrange(b.valid_from_, b.valid_to_, '[)')
			""";

	private static final String PAID_ORDER_OF_DEMO_SENDER = """
			select count(*)
			from order_ o
			         join customer_ u on u.id_ = o.customer_id_
			         join tariff_ t on t.id_ = o.tariff_id_
			where o.id_ = ? and o.type_ = 'SHIPMENT' and o.status_ = 'PAID' and o.price_ = t.shipment_price_
			  and u.keycloak_id_ = ?::uuid
			""";

	private static final String FABRICATED_LEGS = """
			select count(*)
			from reservation_ o
			         join lockermat_cell_ oc on oc.id_ = o.cell_id_
			         join reservation_ d on d.order_id_ = o.order_id_ and d.leg_ = 'DESTINATION'
			         join lockermat_cell_ dc on dc.id_ = d.cell_id_
			where o.order_id_ = ? and o.leg_ = 'ORIGIN' and o.status_ = 'COMPLETED'
			  and oc.lockermat_id_ <> dc.lockermat_id_ and oc.size_ = dc.size_
			  and o.deposited_at_ < o.collected_at_ and o.collected_at_ <= d.deposited_at_ - interval '1 day'
			  and d.status_ = 'OCCUPIED' and d.deposited_at_ = d.from_ and d.collected_at_ is null
			  and d.to_ = d.from_ + interval '3 days'
			""";

	private static final String ORIGINS_IN_OTHER_LOCKERMAT = """
			select count(*)
			from reservation_ o
			         join lockermat_cell_ oc on oc.id_ = o.cell_id_
			         join reservation_ d on d.order_id_ = o.order_id_ and d.leg_ = 'DESTINATION'
			         join lockermat_cell_ dc on dc.id_ = d.cell_id_
			where o.leg_ = 'ORIGIN' and oc.lockermat_id_ <> dc.lockermat_id_
			""";

	private static final String RECIPIENT_CODES = """
			select a.purpose_ || ':' || a.status_ || ':' || a.sent_to_phone_
			from access_code_ a
			         join reservation_ r on r.id_ = a.reservation_id_
			where r.order_id_ = ? and r.leg_ = 'DESTINATION' and a.valid_from_ = r.from_ and a.valid_to_ = r.to_
			""";

	private static final String DESTINATION_PLACE = """
			select l.name_ || '|' || l.address_ || '|' || c.number_
			from reservation_ r
			         join lockermat_cell_ c on c.id_ = r.cell_id_
			         join lockermat_ l on l.id_ = c.lockermat_id_
			where r.id_ = ?
			""";

	private static final String RECIPIENT_EVENT = """
			select count(*)
			from audit_event_
			where entity_ = 'RESERVATION' and entity_id_ = ? and action_ = 'COLLECTED'
			  and actor_ = jsonb_build_object('kind', 'RECIPIENT', 'keycloak_id', ?, 'email', 'jan@example.test', 'phone', ?)
			  and changes_ = jsonb_build_array(jsonb_build_object('f', 'status_', 'old', 'OCCUPIED', 'new', 'COMPLETED'))
			""";

	private static final String INSERT_COLLIDING_CODE = """
			insert into access_code_ (id_, reservation_id_, purpose_, code_hmac_, valid_from_, valid_to_)
			select ?, r.id_, 'DROP_OFF', ?, now(), now() + interval '4 days'
			from reservation_ r
			where r.order_id_ = ?
			""";

	private static final String MOVE_STAY = """
			update reservation_
			set deposited_at_ = now() - make_interval(hours => ?), collected_at_ = now() - make_interval(hours => ?)
			where id_ = ?
			""";

	private final Instant from = Instant.now().plus(Duration.ofDays(1)).truncatedTo(ChronoUnit.SECONDS);
	private final Instant to = from.plus(Duration.ofHours(4));

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JdbcTemplate jdbc;

	@Autowired
	private AccessCodeHmac accessCodeHmac;

	@AfterEach
	void removeOrders() {
		jdbc.execute(TRUNCATE_ORDERS);
	}

	@Test
	void completesTwentySimulateAndPickUpRounds() throws Exception {
		for (int round = 1; round <= 20; round++) {
			JsonNode opening = open(JAN, simulate(JAN).path("reservationId").asLong());

			Assertions.assertEquals("PICK_UP", opening.path("purpose").asString(), "runda " + round);
			Assertions.assertEquals("OPENED", opening.path("result").asString(), "runda " + round);
		}

		Assertions.assertEquals(0, jdbc.queryForObject(SHARED_HMACS_IN_OVERLAPPING_WINDOWS, Integer.class));
		Assertions.assertEquals(20, jdbc.queryForObject(ORIGINS_IN_OTHER_LOCKERMAT, Integer.class));
		Assertions.assertEquals(20, jdbc.queryForObject("select count(*) from order_ where type_ = 'SHIPMENT' and status_ = 'COMPLETED'", Integer.class));
		Assertions.assertEquals(40, jdbc.queryForObject("select count(*) from reservation_ where status_ = 'COMPLETED'", Integer.class));
		Assertions.assertEquals(20, jdbc.queryForObject("select count(*) from access_code_ where status_ = 'USED' and sent_to_phone_ = ?", Integer.class,
				JAN_PHONE));
	}

	@Test
	void retriesSimulationAfterCodeCollision() throws Exception {
		long storageOrderId = book(ANNA);
		long fixtureId = jdbc.queryForObject("select nextval('access_code_id_seq_')", Long.class);
		jdbc.update(INSERT_COLLIDING_CODE, fixtureId, accessCodeHmac.codeHmacOf(accessCodeHmac.pinOf(fixtureId + 1)), storageOrderId);

		JsonNode shipment = simulate(JAN);

		long orderId = shipment.path("orderId").asLong();
		Assertions.assertEquals(storageOrderId + 2, orderId);
		Assertions.assertEquals(List.of(orderId), jdbc.queryForList("select id_ from order_ where type_ = 'SHIPMENT'", Long.class));
		Assertions.assertEquals(1, countRows("shipment_"));
		Assertions.assertEquals(List.of(fixtureId, fixtureId + 2), jdbc.queryForList("select id_ from access_code_ order by id_", Long.class));
		Assertions.assertEquals(5, jdbc.queryForObject("select count(*) from audit_event_ where entity_id_ <> ? or entity_ <> 'ORDER'", Integer.class,
				storageOrderId));
	}

	@Test
	void leavesOrderListsUnchanged() throws Exception {
		book(ANNA);
		book(JAN);
		String annaOrders = get(ANNA, "/api/orders");
		String janOrders = get(JAN, "/api/orders");

		simulate(JAN);

		Assertions.assertEquals(1, JSON.readTree(annaOrders).size());
		Assertions.assertEquals(1, JSON.readTree(janOrders).size());
		Assertions.assertEquals(annaOrders, get(ANNA, "/api/orders"));
		Assertions.assertEquals(janOrders, get(JAN, "/api/orders"));
	}

	@Test
	void fabricatesDeliveredShipmentForCaller() throws Exception {
		JsonNode shipment = simulate(JAN);

		long orderId = shipment.path("orderId").asLong();
		long legId = shipment.path("reservationId").asLong();
		Assertions.assertEquals(Set.of("orderId", "reservationId", "status", "lockermatName", "lockermatAddress", "cellNumber", "from", "to"),
				Set.copyOf(shipment.propertyNames()));
		Assertions.assertEquals("OCCUPIED", shipment.path("status").asString());
		Assertions.assertEquals(jdbc.queryForObject(DESTINATION_PLACE, String.class, legId),
				shipment.path("lockermatName").asString() + "|" + shipment.path("lockermatAddress").asString() + "|" + shipment.path("cellNumber").asInt());
		Assertions.assertEquals(Duration.ofDays(3), Duration.between(Instant.parse(shipment.path("from").asString()), Instant.parse(shipment.path("to").asString())));
		Assertions.assertEquals(1, jdbc.queryForObject(PAID_ORDER_OF_DEMO_SENDER, Integer.class, orderId, DEMO_SENDER));
		Assertions.assertEquals("Jan Nowak|" + JAN_PHONE, jdbc.queryForObject("select recipient_name_ || '|' || recipient_phone_ from shipment_ where order_id_ = ?",
				String.class, orderId));
		Assertions.assertEquals(1, jdbc.queryForObject(FABRICATED_LEGS, Integer.class, orderId));
		Assertions.assertEquals(List.of("PICK_UP:ACTIVE:" + JAN_PHONE), jdbc.queryForList(RECIPIENT_CODES, String.class, orderId));
		Assertions.assertEquals(1, countRows("access_code_"));
		Assertions.assertEquals(List.of("ORDER:CREATED", "ORDER:PAID", "RESERVATION:DEPOSITED", "RESERVATION:COLLECTED", "RESERVATION:DEPOSITED"), auditEvents());
		Assertions.assertEquals(5, jdbc.queryForObject("select count(*) from audit_event_ where actor_ = '{\"kind\": \"SYSTEM\", \"job\": \"simulate-shipment\"}'",
				Integer.class));
		Assertions.assertEquals(List.of(shipment), incoming(JAN));
	}

	@Test
	void letsOnlyRecipientCollectShipment() throws Exception {
		JsonNode shipment = simulate(JAN);
		long orderId = shipment.path("orderId").asLong();
		long legId = shipment.path("reservationId").asLong();

		Assertions.assertEquals(List.of(), incoming(ANNA));
		assertError(openRequest(ANNA, legId), HttpStatus.NOT_FOUND);
		Assertions.assertEquals(0, countRows("cell_opening_"));

		JsonNode opening = open(JAN, legId);

		Assertions.assertEquals("PICK_UP", opening.path("purpose").asString());
		Assertions.assertEquals("OPENED", opening.path("result").asString());
		Assertions.assertEquals("COMPLETED", jdbc.queryForObject("select status_ from reservation_ where id_ = ?", String.class, legId));
		Assertions.assertEquals(1, jdbc.queryForObject("select count(*) from order_ where id_ = ? and status_ = 'COMPLETED' and closed_at_ is not null",
				Integer.class, orderId));
		Assertions.assertEquals(List.of("APP:OPENED:" + JAN), jdbc.queryForList("select channel_ || ':' || result_ || ':' || actor_keycloak_id_ from cell_opening_",
				String.class));
		Assertions.assertEquals(1, jdbc.queryForObject(RECIPIENT_EVENT, Integer.class, legId, JAN, JAN_PHONE));

		assertError(openRequest(JAN, legId), HttpStatus.CONFLICT);
		assertError(openRequest(ANNA, legId), HttpStatus.NOT_FOUND);

		Assertions.assertEquals(1, countRows("cell_opening_"));
		Assertions.assertEquals(List.of("COMPLETED"), incoming(JAN).stream().map(item -> item.path("status").asString()).toList());
		Assertions.assertEquals(List.of(), incoming(ANNA));
	}

	@Test
	void listsShipmentsCollectedInLast24Hours() throws Exception {
		long oldLegId = simulateAndCollect(JAN);
		long recentLegId = simulateAndCollect(JAN);
		long waitingLegId = simulate(JAN).path("reservationId").asLong();
		jdbc.update(MOVE_STAY, 26, 25, oldLegId);
		jdbc.update(MOVE_STAY, 2, 1, recentLegId);

		List<JsonNode> items = incoming(JAN);

		Assertions.assertEquals(List.of(waitingLegId, recentLegId), items.stream().map(item -> item.path("reservationId").asLong()).toList());
		Assertions.assertEquals(List.of("OCCUPIED", "COMPLETED"), items.stream().map(item -> item.path("status").asString()).toList());
	}

	private long simulateAndCollect(String subject) throws Exception {
		long legId = simulate(subject).path("reservationId").asLong();
		open(subject, legId);
		return legId;
	}

	private JsonNode simulate(String subject) throws Exception {
		return JSON.readTree(perform(post(subject, "/api/dev/shipments"), HttpStatus.CREATED));
	}

	private JsonNode open(String subject, long reservationId) throws Exception {
		return JSON.readTree(perform(openRequest(subject, reservationId), HttpStatus.OK));
	}

	private MockHttpServletRequestBuilder openRequest(String subject, long reservationId) {
		return post(subject, "/api/reservations/" + reservationId + "/open");
	}

	private long book(String subject) throws Exception {
		Map<String, Object> order = Map.of("lockermatId", lockermatId(), "size", "S", "from", from.toString(), "to", to.toString());
		MockHttpServletRequestBuilder request = post(subject, "/api/orders")
				.contentType(MediaType.APPLICATION_JSON)
				.content(JSON.writeValueAsString(order));
		return JSON.readTree(perform(request, HttpStatus.CREATED)).path("id").asLong();
	}

	private List<JsonNode> incoming(String subject) throws Exception {
		List<JsonNode> items = new ArrayList<>();
		JSON.readTree(get(subject, "/api/shipments/incoming")).forEach(items::add);
		return items;
	}

	private String get(String subject, String path) throws Exception {
		return perform(as(subject, MockMvcRequestBuilders.get(path)), HttpStatus.OK);
	}

	private MockHttpServletRequestBuilder post(String subject, String path) {
		return as(subject, MockMvcRequestBuilders.post(path)).with(SecurityMockMvcRequestPostProcessors.csrf());
	}

	private MockHttpServletRequestBuilder as(String subject, MockHttpServletRequestBuilder request) {
		List<String> user = USERS.get(subject);
		return request.with(SecurityMockMvcRequestPostProcessors.jwt().jwt(jwt -> jwt.subject(subject).claim("email", user.get(0)).claim("name", user.get(1))));
	}

	private String perform(MockHttpServletRequestBuilder request, HttpStatus status) throws Exception {
		MvcResult result = mockMvc.perform(request).andReturn();
		String body = result.getResponse().getContentAsString(StandardCharsets.UTF_8);
		Assertions.assertEquals(status.value(), result.getResponse().getStatus(), body);
		return body;
	}

	private void assertError(MockHttpServletRequestBuilder request, HttpStatus status) throws Exception {
		JsonNode error = JSON.readTree(perform(request, status));
		Assertions.assertEquals(status.name(), error.path("code").asString());
		Assertions.assertFalse(error.path("message").asString().isBlank());
	}

	private List<String> auditEvents() {
		return jdbc.queryForList("select entity_ || ':' || action_ from audit_event_ order by id_", String.class);
	}

	private int countRows(String table) {
		return jdbc.queryForObject("select count(*) from " + table, Integer.class);
	}

	private long lockermatId() {
		return jdbc.queryForObject("select id_ from lockermat_ where code_ = ?", Long.class, LOCKERMAT);
	}
}
