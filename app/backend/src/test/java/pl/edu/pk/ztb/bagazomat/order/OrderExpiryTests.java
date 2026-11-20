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
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.time.Duration;
import java.time.Instant;
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
class OrderExpiryTests {

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

	@Autowired
	private DataSource dataSource;

	@Autowired
	private OrderExpiryJob orderExpiryJob;

	@AfterEach
	void removeOrders() {
		jdbc.execute(TRUNCATE_ORDERS);
	}

	@Test
	void expiredLegStopsBlockingItsCell() throws Exception {
		JsonNode expiring = JSON.readTree(perform(bookRequest(ANNA, "L"), HttpStatus.CREATED));
		long expiringId = expiring.path("id").asLong();
		long waitingId = book(JAN, "L");
		passDeadline(expiringId);
		Assertions.assertEquals(HttpStatus.CONFLICT.value(), mockMvc.perform(bookRequest(ANNA, "L")).andReturn().getResponse().getStatus());

		orderExpiryJob.expireOverdueOrders();

		Assertions.assertEquals(1, jdbc.queryForObject("select count(*) from order_ where id_ = ? and status_ = 'EXPIRED' and closed_at_ is not null",
				Integer.class, expiringId));
		Assertions.assertEquals(List.of("CANCELLED"), legStatuses(expiringId));
		Assertions.assertEquals("AWAITING_PAYMENT", orderStatus(waitingId));
		Assertions.assertEquals(List.of("BOOKED"), legStatuses(waitingId));
		JsonNode rebooked = JSON.readTree(perform(bookRequest(ANNA, "L"), HttpStatus.CREATED));
		Assertions.assertEquals(expiring.path("cellNumber").asInt(), rebooked.path("cellNumber").asInt());
	}

	@Test
	void writesExpiryEventWithSystemActor() throws Exception {
		long id = book(ANNA, "S");
		passDeadline(id);

		orderExpiryJob.expireOverdueOrders();
		orderExpiryJob.expireOverdueOrders();

		Assertions.assertEquals(List.of("CREATED", "EXPIRED"), jdbc.queryForList("select action_ from audit_event_ order by id_", String.class));
		Assertions.assertEquals(1, jdbc.queryForObject("""
				select count(*)
				from audit_event_
				where entity_ = 'ORDER' and entity_id_ = ? and action_ = 'EXPIRED'
				  and actor_ = '{"kind": "SYSTEM", "job": "expire-orders"}'::jsonb
				  and changes_ = '[{"f": "status_", "old": "AWAITING_PAYMENT", "new": "EXPIRED"}]'::jsonb
				""", Integer.class, id));
	}

	@Test
	void keepsPaidOrderPastItsDeadline() throws Exception {
		long id = book(ANNA, "S");
		perform(post(ANNA, "/api/orders/" + id + "/payments")
				.contentType(MediaType.APPLICATION_JSON)
				.content(JSON.writeValueAsString(Map.of("result", "SUCCESS"))), HttpStatus.CREATED);
		passDeadline(id);

		orderExpiryJob.expireOverdueOrders();

		Assertions.assertEquals("PAID", orderStatus(id));
		Assertions.assertEquals(List.of("BOOKED"), legStatuses(id));
		Assertions.assertEquals(List.of("CREATED", "PAID"), jdbc.queryForList("select action_ from audit_event_ order by id_", String.class));
	}

	@Test
	void skipsOrderPaidWhileExpiryWaitsForLock() throws Exception {
		long id = book(ANNA, "S");
		passDeadline(id);

		expireWhilePaidInOtherTransaction(id);

		Assertions.assertEquals("PAID", orderStatus(id));
		Assertions.assertEquals(List.of("BOOKED"), legStatuses(id));
		Assertions.assertEquals(List.of("CREATED"), jdbc.queryForList("select action_ from audit_event_ order by id_", String.class));
	}

	@Test
	void refusesCancelOfExpiredOrder() throws Exception {
		long id = book(ANNA, "S");
		passDeadline(id);
		orderExpiryJob.expireOverdueOrders();

		MvcResult result = mockMvc.perform(post(ANNA, "/api/orders/" + id + "/cancel")).andReturn();

		Assertions.assertEquals(HttpStatus.CONFLICT.value(), result.getResponse().getStatus());
		Assertions.assertEquals("EXPIRED", orderStatus(id));
	}

	private void expireWhilePaidInOtherTransaction(long orderId) throws Exception {
		try (ExecutorService executor = Executors.newSingleThreadExecutor(); Connection holder = dataSource.getConnection()) {
			holder.setAutoCommit(false);
			try (PreparedStatement payment = holder.prepareStatement("update order_ set status_ = 'PAID' where id_ = ?")) {
				payment.setLong(1, orderId);
				payment.executeUpdate();
			}
			Future<?> expiry = executor.submit(orderExpiryJob::expireOverdueOrders);
			awaitLockWait();
			holder.commit();
			expiry.get(30, TimeUnit.SECONDS);
		}
	}

	private void awaitLockWait() throws InterruptedException {
		Instant limit = Instant.now().plus(Duration.ofSeconds(10));
		while (jdbc.queryForObject("select count(*) from pg_locks where not granted", Integer.class) == 0) {
			Assertions.assertTrue(Instant.now().isBefore(limit), "Zadanie nie czeka na blokadę zamówienia");
			Thread.sleep(20);
		}
	}

	private void passDeadline(long orderId) {
		jdbc.update("update order_ set payment_deadline_ = created_at_ + interval '1 microsecond' where id_ = ?", orderId);
	}

	private long book(String subject, String size) throws Exception {
		return JSON.readTree(perform(bookRequest(subject, size), HttpStatus.CREATED)).path("id").asLong();
	}

	private MockHttpServletRequestBuilder bookRequest(String subject, String size) {
		Map<String, Object> order = Map.of("lockermatId", lockermatId(), "size", size, "from", from.toString(), "to", to.toString());
		return post(subject, "/api/orders")
				.contentType(MediaType.APPLICATION_JSON)
				.content(JSON.writeValueAsString(order));
	}

	private MockHttpServletRequestBuilder post(String subject, String path) {
		String email = subject.equals(ANNA) ? "anna@example.test" : "jan@example.test";
		return MockMvcRequestBuilders.post(path)
				.with(SecurityMockMvcRequestPostProcessors.jwt().jwt(jwt -> jwt.subject(subject).claim("email", email)))
				.with(SecurityMockMvcRequestPostProcessors.csrf());
	}

	private String perform(MockHttpServletRequestBuilder request, HttpStatus status) throws Exception {
		MvcResult result = mockMvc.perform(request).andReturn();
		String body = result.getResponse().getContentAsString(StandardCharsets.UTF_8);
		Assertions.assertEquals(status.value(), result.getResponse().getStatus(), body);
		return body;
	}

	private List<String> legStatuses(long orderId) {
		return jdbc.queryForList("select status_ from reservation_ where order_id_ = ?", String.class, orderId);
	}

	private String orderStatus(long id) {
		return jdbc.queryForObject("select status_ from order_ where id_ = ?", String.class, id);
	}

	private long lockermatId() {
		return jdbc.queryForObject("select id_ from lockermat_ where code_ = ?", Long.class, LOCKERMAT);
	}
}
