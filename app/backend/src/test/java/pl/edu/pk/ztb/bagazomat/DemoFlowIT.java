package pl.edu.pk.ztb.bagazomat;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
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
import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** @author Anton Gorokh */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("dev")
@Import(PostgresContainerConfiguration.class)
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class DemoFlowIT {

	private static final Logger LOG = LoggerFactory.getLogger(DemoFlowIT.class);

	private static final String ANNA = TestRows.ANNA.toString();
	private static final String JAN = "a4bba234-ddf1-5dbc-bf7d-fca171bfe08f";
	private static final Map<String, List<String>> USERS = Map.of(
			ANNA, List.of("anna@example.test", "Anna Kowalska"),
			JAN, List.of("jan@example.test", "Jan Nowak"));
	private static final String LOCKERMAT = "KRK-GLOWNY";

	private static final JsonMapper JSON = JsonMapper.builder()
			.enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS)
			.build();

	private static final String TRUNCATE_ORDERS = """
			truncate order_, reservation_, shipment_, payment_, access_code_, incident_, cell_opening_, audit_event_
			""";

	private final Instant now = Instant.now().truncatedTo(ChronoUnit.SECONDS);
	private final Instant from = now.minus(Duration.ofMinutes(1));
	private final Instant to = now.plus(Duration.ofHours(4));

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JdbcTemplate jdbc;

	@AfterEach
	void removeOrders() {
		jdbc.execute(TRUNCATE_ORDERS);
	}

	@Test
	@Order(1)
	void storesLuggageAndListsHistory() throws Exception {
		JsonNode order = book(ANNA);
		long orderId = order.path("id").asLong();
		long legId = order.path("reservationId").asLong();
		LOG.info("Przechowanie 1/6, rezerwacja: {}, {}, skrytka {} nr {}, {}–{}, {} zł, {}", order.path("number").asString(),
				order.path("lockermatName").asString(), order.path("size").asString(), order.path("cellNumber").asInt(), order.path("from").asString(),
				order.path("to").asString(), order.path("price").decimalValue(), order.path("status").asString());
		Assertions.assertEquals("AWAITING_PAYMENT", order.path("status").asString());

		JsonNode payment = pay(ANNA, orderId);
		LOG.info("Przechowanie 2/6, płatność: {}, {} zł", payment.path("status").asString(), payment.path("amount").decimalValue());
		Assertions.assertEquals("COMPLETED", payment.path("status").asString());

		JsonNode dropOff = open(ANNA, legId);
		LOG.info("Przechowanie 3/6, nadanie bagażu: {} {}", dropOff.path("purpose").asString(), dropOff.path("result").asString());
		assertOpened("DROP_OFF", dropOff);

		JsonNode pickUp = open(ANNA, legId);
		LOG.info("Przechowanie 4/6, odbiór bagażu: {} {}", pickUp.path("purpose").asString(), pickUp.path("result").asString());
		assertOpened("PICK_UP", pickUp);

		List<String> history = history(ANNA, orderId);
		LOG.info("Przechowanie 5/6, historia: {}", String.join(", ", history));
		Assertions.assertEquals(List.of("ORDER:CREATED:CUSTOMER", "ORDER:PAID:CUSTOMER", "RESERVATION:DEPOSITED:CUSTOMER", "RESERVATION:COLLECTED:CUSTOMER"),
				history);

		JsonNode error = assertError(historyRequest(JAN, orderId), HttpStatus.NOT_FOUND);
		LOG.info("Przechowanie 6/6, historia zamówienia anny dla jana: {}", error.path("code").asString());
	}

	@Test
	@Order(2)
	void deliversShipmentAndListsHistory() throws Exception {
		JsonNode shipment = simulate(JAN);
		long orderId = shipment.path("orderId").asLong();
		LOG.info("Przesyłka 1/4, symulacja: zamówienie {}, {}, skrytka nr {}, {}–{}, {}", orderId, shipment.path("lockermatName").asString(),
				shipment.path("cellNumber").asInt(), shipment.path("from").asString(), shipment.path("to").asString(), shipment.path("status").asString());
		Assertions.assertEquals("OCCUPIED", shipment.path("status").asString());

		JsonNode pickUp = open(JAN, shipment.path("reservationId").asLong());
		LOG.info("Przesyłka 2/4, odbiór przesyłki: {} {}", pickUp.path("purpose").asString(), pickUp.path("result").asString());
		assertOpened("PICK_UP", pickUp);

		List<String> history = history(JAN, orderId);
		LOG.info("Przesyłka 3/4, historia: {}", String.join(", ", history));
		Assertions.assertEquals(List.of("ORDER:CREATED:SYSTEM", "ORDER:PAID:SYSTEM", "RESERVATION:DEPOSITED:SYSTEM", "RESERVATION:COLLECTED:SYSTEM",
				"RESERVATION:DEPOSITED:SYSTEM", "RESERVATION:COLLECTED:RECIPIENT"), history);

		JsonNode error = assertError(historyRequest(ANNA, orderId), HttpStatus.NOT_FOUND);
		LOG.info("Przesyłka 4/4, historia przesyłki jana dla anny: {}", error.path("code").asString());
	}

	private void assertOpened(String purpose, JsonNode opening) {
		Assertions.assertEquals(purpose, opening.path("purpose").asString());
		Assertions.assertEquals("OPENED", opening.path("result").asString());
	}

	private JsonNode book(String subject) throws Exception {
		Map<String, Object> order = Map.of("lockermatId", lockermatId(), "size", "S", "from", from.toString(), "to", to.toString());
		MockHttpServletRequestBuilder request = post(subject, "/api/orders")
				.contentType(MediaType.APPLICATION_JSON)
				.content(JSON.writeValueAsString(order));
		return JSON.readTree(perform(request, HttpStatus.CREATED));
	}

	private JsonNode pay(String subject, long orderId) throws Exception {
		MockHttpServletRequestBuilder request = post(subject, "/api/orders/" + orderId + "/payments")
				.contentType(MediaType.APPLICATION_JSON)
				.content(JSON.writeValueAsString(Map.of("result", "SUCCESS")));
		return JSON.readTree(perform(request, HttpStatus.CREATED));
	}

	private JsonNode open(String subject, long reservationId) throws Exception {
		return JSON.readTree(perform(post(subject, "/api/reservations/" + reservationId + "/open"), HttpStatus.OK));
	}

	private JsonNode simulate(String subject) throws Exception {
		return JSON.readTree(perform(post(subject, "/api/dev/shipments"), HttpStatus.CREATED));
	}

	private List<String> history(String subject, long orderId) throws Exception {
		List<String> events = new ArrayList<>();
		for (JsonNode event : JSON.readTree(perform(historyRequest(subject, orderId), HttpStatus.OK))) {
			events.add(event.path("entity").asString() + ":" + event.path("action").asString() + ":" + event.path("actorKind").asString());
		}
		return events;
	}

	private MockHttpServletRequestBuilder historyRequest(String subject, long orderId) {
		return as(subject, MockMvcRequestBuilders.get("/api/orders/" + orderId + "/history"));
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

	private JsonNode assertError(MockHttpServletRequestBuilder request, HttpStatus status) throws Exception {
		JsonNode error = JSON.readTree(perform(request, status));
		Assertions.assertEquals(status.name(), error.path("code").asString());
		Assertions.assertFalse(error.path("message").asString().isBlank());
		return error;
	}

	private long lockermatId() {
		return jdbc.queryForObject("select id_ from lockermat_ where code_ = ?", Long.class, LOCKERMAT);
	}
}
