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
import pl.edu.pk.ztb.bagazomat.PostgresContainerConfiguration;
import pl.edu.pk.ztb.bagazomat.TestRows;
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
@Import(PostgresContainerConfiguration.class)
class OrderHistoryTests {

	private static final String ANNA = TestRows.ANNA.toString();
	private static final String JAN = "a4bba234-ddf1-5dbc-bf7d-fca171bfe08f";
	private static final String LOCKERMAT = "KRK-GLOWNY";

	private static final JsonMapper JSON = JsonMapper.builder().build();

	private static final String TRUNCATE_ORDERS = """
			truncate order_, reservation_, shipment_, payment_, access_code_, incident_, cell_opening_, audit_event_
			""";

	private final Instant from = Instant.now().plus(Duration.ofDays(1)).truncatedTo(ChronoUnit.SECONDS);
	private final Instant to = from.plus(Duration.ofHours(4));

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JdbcTemplate jdbc;

	@AfterEach
	void removeOrders() {
		jdbc.execute(TRUNCATE_ORDERS);
	}

	@Test
	void listsEventsOfOrderLegsAndPaymentsOldestFirst() throws Exception {
		long id = book(ANNA);
		pay(ANNA, id);
		perform(post(ANNA, "/api/orders/" + id + "/cancel"), HttpStatus.OK);
		book(ANNA);
		book(JAN);

		List<JsonNode> history = history(ANNA, id);

		Assertions.assertEquals(List.of("ORDER:CREATED:CUSTOMER", "ORDER:PAID:CUSTOMER", "ORDER:CANCELLED:CUSTOMER", "PAYMENT:REFUNDED:CUSTOMER"),
				history.stream().map(this::describe).toList());
		Assertions.assertEquals(Set.of("id", "at", "entity", "action", "actorKind"), Set.copyOf(history.getFirst().propertyNames()));
		Assertions.assertEquals(jdbc.queryForList("select id_ from audit_event_ where action_ <> 'CREATED' or entity_id_ = ? order by id_", Long.class, id),
				history.stream().map(event -> event.path("id").asLong()).toList());
		Assertions.assertEquals(history.stream().map(this::atOf).sorted().toList(), history.stream().map(this::atOf).toList());
	}

	@Test
	void hidesHistoryFromOthers() throws Exception {
		long id = book(ANNA);

		assertError(historyRequest(JAN, id), HttpStatus.NOT_FOUND);
		assertError(historyRequest(ANNA, id + 1), HttpStatus.NOT_FOUND);
	}

	private String describe(JsonNode event) {
		return event.path("entity").asString() + ":" + event.path("action").asString() + ":" + event.path("actorKind").asString();
	}

	private Instant atOf(JsonNode event) {
		return Instant.parse(event.path("at").asString());
	}

	private long book(String subject) throws Exception {
		Map<String, Object> order = Map.of("lockermatId", lockermatId(), "size", "S", "from", from.toString(), "to", to.toString());
		MockHttpServletRequestBuilder request = post(subject, "/api/orders")
				.contentType(MediaType.APPLICATION_JSON)
				.content(JSON.writeValueAsString(order));
		return JSON.readTree(perform(request, HttpStatus.CREATED)).path("id").asLong();
	}

	private void pay(String subject, long orderId) throws Exception {
		MockHttpServletRequestBuilder request = post(subject, "/api/orders/" + orderId + "/payments")
				.contentType(MediaType.APPLICATION_JSON)
				.content(JSON.writeValueAsString(Map.of("result", "SUCCESS")));
		perform(request, HttpStatus.CREATED);
	}

	private List<JsonNode> history(String subject, long orderId) throws Exception {
		List<JsonNode> events = new ArrayList<>();
		JSON.readTree(perform(historyRequest(subject, orderId), HttpStatus.OK)).forEach(events::add);
		return events;
	}

	private MockHttpServletRequestBuilder historyRequest(String subject, long orderId) {
		return as(subject, MockMvcRequestBuilders.get("/api/orders/" + orderId + "/history"));
	}

	private MockHttpServletRequestBuilder post(String subject, String path) {
		return as(subject, MockMvcRequestBuilders.post(path)).with(SecurityMockMvcRequestPostProcessors.csrf());
	}

	private MockHttpServletRequestBuilder as(String subject, MockHttpServletRequestBuilder request) {
		String email = subject.equals(ANNA) ? "anna@example.test" : "jan@example.test";
		return request.with(SecurityMockMvcRequestPostProcessors.jwt().jwt(jwt -> jwt.subject(subject).claim("email", email)));
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

	private long lockermatId() {
		return jdbc.queryForObject("select id_ from lockermat_ where code_ = ?", Long.class, LOCKERMAT);
	}
}
