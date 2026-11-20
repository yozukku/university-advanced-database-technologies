package pl.edu.pk.ztb.bagazomat.order;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.mockito.stubbing.Answer;
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
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders;
import org.springframework.test.web.servlet.result.MockMvcResultMatchers;
import pl.edu.pk.ztb.bagazomat.PostgresContainerConfiguration;
import pl.edu.pk.ztb.bagazomat.TestRows;
import pl.edu.pk.ztb.bagazomat.lockermat.CellSize;
import pl.edu.pk.ztb.bagazomat.lockermat.LockermatCellRepository;
import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.temporal.ChronoUnit;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/** @author Anton Gorokh */
@SpringBootTest
@AutoConfigureMockMvc
@Import(PostgresContainerConfiguration.class)
class OrderApiTests {

	private static final String ANNA = TestRows.ANNA.toString();
	private static final String JAN = "a4bba234-ddf1-5dbc-bf7d-fca171bfe08f";
	private static final String LOCKERMAT = "KRK-GLOWNY";

	private static final JsonMapper JSON = JsonMapper.builder()
			.enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS)
			.build();

	private static final String TRUNCATE_ORDERS = """
			truncate order_, reservation_, shipment_, payment_, access_code_, incident_, cell_opening_, audit_event_
			""";

	private static final String INSERT_SHIPMENT_ORDER = """
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

	private final Instant from = Instant.now().plus(Duration.ofDays(1)).truncatedTo(ChronoUnit.SECONDS);
	private final Instant to = from.plus(Duration.ofHours(4));

	@MockitoSpyBean
	private LockermatCellRepository lockermatCellRepository;

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JdbcTemplate jdbc;

	@AfterEach
	void removeOrders() {
		jdbc.execute(TRUNCATE_ORDERS);
	}

	@Test
	void refusesSecondBookingOfLastCell() throws Exception {
		book(JAN, CellSize.L, from, to);
		JsonNode last = book(ANNA, CellSize.L, from, to);

		assertError(post(ANNA, CellSize.L, from, to), HttpStatus.CONFLICT, "CONFLICT");

		Assertions.assertEquals(12, last.path("cellNumber").asInt());
		Assertions.assertEquals(2, countRows("order_"));
		Assertions.assertEquals(2, countRows("reservation_"));
		Assertions.assertEquals(2, countRows("audit_event_"));
	}

	@Test
	void retriesForcedConflictWithNextCell() throws Exception {
		long janOrder = book(JAN, CellSize.S, from, to).path("id").asLong();
		Answer<?> realPicker = Mockito.mockingDetails(lockermatCellRepository).getMockCreationSettings().getDefaultAnswer();
		Mockito.doReturn(Optional.of(cellId(1)))
				.doAnswer(realPicker)
				.when(lockermatCellRepository)
				.findFreeCell(Mockito.anyLong(), Mockito.anyString(), Mockito.any(), Mockito.any());

		JsonNode order = book(ANNA, CellSize.S, from, to);

		Assertions.assertEquals(2, order.path("cellNumber").asInt());
		Assertions.assertEquals(janOrder + 2, order.path("id").asLong());
		Assertions.assertEquals(List.of(janOrder, janOrder + 2), jdbc.queryForList("select id_ from order_ order by id_", Long.class));
		Assertions.assertEquals(List.of(janOrder, janOrder + 2), jdbc.queryForList("select entity_id_ from audit_event_ order by entity_id_", Long.class));
		Mockito.verify(lockermatCellRepository, Mockito.times(3)).findFreeCell(Mockito.anyLong(), Mockito.anyString(), Mockito.any(), Mockito.any());
	}

	@Test
	void givesUpAfterThreeConflicts() throws Exception {
		book(JAN, CellSize.S, from, to);
		Mockito.doReturn(Optional.of(cellId(1)))
				.when(lockermatCellRepository)
				.findFreeCell(Mockito.anyLong(), Mockito.anyString(), Mockito.any(), Mockito.any());

		assertError(post(ANNA, CellSize.S, from, to), HttpStatus.CONFLICT, "CONFLICT");

		Assertions.assertEquals(1, countRows("order_"));
		Assertions.assertEquals(1, countRows("audit_event_"));
		Mockito.verify(lockermatCellRepository, Mockito.times(4)).findFreeCell(Mockito.anyLong(), Mockito.anyString(), Mockito.any(), Mockito.any());
	}

	@Test
	void hidesOrderFromOtherCustomer() throws Exception {
		long id = book(ANNA, CellSize.M, from, to).path("id").asLong();

		Assertions.assertEquals(id, getOk(ANNA, "/api/orders/" + id).path("id").asLong());
		assertError(get(JAN, "/api/orders/" + id), HttpStatus.NOT_FOUND, "NOT_FOUND");
		assertError(get(ANNA, "/api/orders/" + (id + 1)), HttpStatus.NOT_FOUND, "NOT_FOUND");
		Assertions.assertEquals(0, getOk(JAN, "/api/orders").size());
	}

	@Test
	void writesCreatedEventWithCustomerActor() throws Exception {
		long id = book(ANNA, CellSize.S, from, to).path("id").asLong();

		Assertions.assertEquals(1, jdbc.queryForObject("""
				select count(*)
				from audit_event_
				where entity_ = 'ORDER' and entity_id_ = ? and action_ = 'CREATED'
				  and actor_ = jsonb_build_object('kind', 'CUSTOMER', 'keycloak_id', ?, 'email', 'anna@example.test')
				  and changes_ = '[{"f": "status_", "old": null, "new": "AWAITING_PAYMENT"}]'::jsonb
				""", Integer.class, id, ANNA));
		Assertions.assertEquals(1, countRows("audit_event_"));
	}

	@Test
	void describesBookedOrder() throws Exception {
		Instant end = from.plus(Duration.ofHours(25));

		JsonNode order = book(ANNA, CellSize.S, from, end);

		Assertions.assertEquals(Set.of("id", "number", "status", "size", "price", "paymentDeadline", "createdAt", "reservationId", "reservationStatus",
				"from", "to", "lockermatName", "lockermatAddress", "cellNumber"), Set.copyOf(order.propertyNames()));
		Assertions.assertEquals("BAG-%010d".formatted(order.path("id").asLong()), order.path("number").asString());
		Assertions.assertEquals("AWAITING_PAYMENT", order.path("status").asString());
		Assertions.assertEquals("BOOKED", order.path("reservationStatus").asString());
		Assertions.assertEquals("S", order.path("size").asString());
		Assertions.assertEquals(new BigDecimal("30.00"), order.path("price").decimalValue());
		Assertions.assertEquals(from, instant(order, "from"));
		Assertions.assertEquals(end, instant(order, "to"));
		Assertions.assertEquals("Kraków Główny", order.path("lockermatName").asString());
		Assertions.assertEquals(1, order.path("cellNumber").asInt());
		Assertions.assertEquals(Duration.ofMinutes(15), Duration.between(instant(order, "createdAt"), instant(order, "paymentDeadline")));
	}

	@Test
	void capsPaymentDeadlineAtReservationEnd() throws Exception {
		Instant start = Instant.now().truncatedTo(ChronoUnit.SECONDS);
		Instant end = start.plus(Duration.ofMinutes(10));

		JsonNode order = book(ANNA, CellSize.S, start, end);

		Assertions.assertEquals(end, instant(order, "paymentDeadline"));
	}

	@Test
	void rejectsEndedEmptyAndIncompleteWindows() throws Exception {
		Instant now = Instant.now();

		assertError(post(ANNA, CellSize.S, now.minus(Duration.ofHours(2)), now.minus(Duration.ofMinutes(1))), HttpStatus.BAD_REQUEST, "BAD_REQUEST");
		assertError(post(ANNA, CellSize.S, from, from), HttpStatus.BAD_REQUEST, "BAD_REQUEST");
		assertError(post(ANNA, Map.of("lockermatId", lockermatId(), "from", from.toString(), "to", to.toString())), HttpStatus.BAD_REQUEST, "BAD_REQUEST");
		assertError(post(ANNA, Map.of("lockermatId", lockermatId(), "size", "XL", "from", from.toString(), "to", to.toString())), HttpStatus.BAD_REQUEST,
				"BAD_REQUEST");

		Assertions.assertEquals(0, countRows("order_"));
	}

	@Test
	void listsOwnStorageOrdersNewestFirst() throws Exception {
		long first = book(ANNA, CellSize.S, from, to).path("id").asLong();
		book(JAN, CellSize.S, from, to);
		long second = book(ANNA, CellSize.M, from, to).path("id").asLong();
		jdbc.update(INSERT_SHIPMENT_ORDER, TestRows.ANNA, from.atOffset(ZoneOffset.UTC), to.atOffset(ZoneOffset.UTC), LOCKERMAT);

		List<Long> ids = getOk(ANNA, "/api/orders").valueStream()
				.map(order -> order.path("id").asLong())
				.toList();

		Assertions.assertEquals(List.of(second, first), ids);
	}

	private JsonNode book(String subject, CellSize size, Instant windowFrom, Instant windowTo) throws Exception {
		String body = mockMvc.perform(post(subject, size, windowFrom, windowTo))
				.andExpect(MockMvcResultMatchers.status().isCreated())
				.andReturn()
				.getResponse()
				.getContentAsString(StandardCharsets.UTF_8);
		return JSON.readTree(body);
	}

	private MockHttpServletRequestBuilder post(String subject, CellSize size, Instant windowFrom, Instant windowTo) {
		Map<String, Object> order = new LinkedHashMap<>();
		order.put("lockermatId", lockermatId());
		order.put("size", size.name());
		order.put("from", windowFrom.toString());
		order.put("to", windowTo.toString());
		return post(subject, order);
	}

	private MockHttpServletRequestBuilder post(String subject, Map<String, Object> order) {
		return as(subject, MockMvcRequestBuilders.post("/api/orders"))
				.with(SecurityMockMvcRequestPostProcessors.csrf())
				.contentType(MediaType.APPLICATION_JSON)
				.content(JSON.writeValueAsString(order));
	}

	private MockHttpServletRequestBuilder get(String subject, String path) {
		return as(subject, MockMvcRequestBuilders.get(path));
	}

	private JsonNode getOk(String subject, String path) throws Exception {
		String body = mockMvc.perform(get(subject, path))
				.andExpect(MockMvcResultMatchers.status().isOk())
				.andReturn()
				.getResponse()
				.getContentAsString(StandardCharsets.UTF_8);
		return JSON.readTree(body);
	}

	private MockHttpServletRequestBuilder as(String subject, MockHttpServletRequestBuilder request) {
		String email = subject.equals(ANNA) ? "anna@example.test" : "jan@example.test";
		return request.with(SecurityMockMvcRequestPostProcessors.jwt().jwt(jwt -> jwt.subject(subject).claim("email", email)));
	}

	private void assertError(MockHttpServletRequestBuilder request, HttpStatus status, String code) throws Exception {
		String body = mockMvc.perform(request)
				.andExpect(MockMvcResultMatchers.status().is(status.value()))
				.andReturn()
				.getResponse()
				.getContentAsString(StandardCharsets.UTF_8);
		JsonNode error = JSON.readTree(body);
		Assertions.assertEquals(code, error.path("code").asString(), body);
		Assertions.assertFalse(error.path("message").asString().isBlank(), body);
	}

	private Instant instant(JsonNode order, String field) {
		return Instant.parse(order.path(field).asString());
	}

	private int countRows(String table) {
		return jdbc.queryForObject("select count(*) from " + table, Integer.class);
	}

	private long lockermatId() {
		return jdbc.queryForObject("select id_ from lockermat_ where code_ = ?", Long.class, LOCKERMAT);
	}

	private long cellId(int number) {
		return jdbc.queryForObject("""
				select c.id_
				from lockermat_cell_ c
				         join lockermat_ l on l.id_ = c.lockermat_id_
				where l.code_ = ? and c.number_ = ?
				""", Long.class, LOCKERMAT, number);
	}
}
