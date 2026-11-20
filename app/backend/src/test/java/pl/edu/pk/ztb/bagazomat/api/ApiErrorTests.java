package pl.edu.pk.ztb.bagazomat.api;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders;
import org.springframework.test.web.servlet.result.MockMvcResultMatchers;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;
import pl.edu.pk.ztb.bagazomat.PostgresContainerConfiguration;
import pl.edu.pk.ztb.bagazomat.TestRows;
import pl.edu.pk.ztb.bagazomat.order.Order;
import pl.edu.pk.ztb.bagazomat.order.OrderRepository;
import pl.edu.pk.ztb.bagazomat.order.ReservationRepository;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.regex.Pattern;

/** @author Anton Gorokh */
@SpringBootTest
@AutoConfigureMockMvc
@Import({PostgresContainerConfiguration.class, ApiErrorTests.FailingWritesController.class})
class ApiErrorTests {

	private static final Pattern SQL_TEXT = Pattern.compile(
			"insert|select|duplicate|violates|constraint|sql|order_|reservation_|__uq|__ex|__ck|23505|23P01|23514", Pattern.CASE_INSENSITIVE);

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JdbcTemplate jdbc;

	@Test
	void answersDuplicateKeyWithConflict() throws Exception {
		assertError("/test/duplicate-order", HttpStatus.CONFLICT, "CONFLICT");
	}

	@Test
	void answersExclusionViolationWithConflict() throws Exception {
		assertError("/test/double-booking", HttpStatus.CONFLICT, "CONFLICT");
	}

	@Test
	void answersOtherIntegrityViolationWithInternalError() throws Exception {
		assertError("/test/empty-window", HttpStatus.INTERNAL_SERVER_ERROR, "INTERNAL_ERROR");
	}

	private void assertError(String path, HttpStatus status, String code) throws Exception {
		String body = mockMvc.perform(MockMvcRequestBuilders.post(path)
						.with(SecurityMockMvcRequestPostProcessors.jwt().jwt(jwt -> jwt.subject(TestRows.ANNA.toString())))
						.with(SecurityMockMvcRequestPostProcessors.csrf()))
				.andExpect(MockMvcResultMatchers.status().is(status.value()))
				.andReturn()
				.getResponse()
				.getContentAsString(StandardCharsets.UTF_8);

		JsonNode error = JsonMapper.shared().readTree(body);
		Assertions.assertEquals(List.of("code", "message"), List.copyOf(error.propertyNames()), body);
		Assertions.assertEquals(code, error.path("code").asString());
		Assertions.assertFalse(error.path("message").asString().isBlank(), body);
		Assertions.assertFalse(SQL_TEXT.matcher(body).find(), body);
		Assertions.assertEquals(0, jdbc.queryForObject("select count(*) from order_", Integer.class));
	}

	@RestController
	static class FailingWritesController {

		private final TransactionTemplate transactionTemplate;
		private final OrderRepository orderRepository;
		private final ReservationRepository reservationRepository;
		private final JdbcTemplate jdbc;

		FailingWritesController(TransactionTemplate transactionTemplate, OrderRepository orderRepository, ReservationRepository reservationRepository,
				JdbcTemplate jdbc) {
			this.transactionTemplate = transactionTemplate;
			this.orderRepository = orderRepository;
			this.reservationRepository = reservationRepository;
			this.jdbc = jdbc;
		}

		@PostMapping("/test/duplicate-order")
		public void insertDuplicateOrder() {
			transactionTemplate.executeWithoutResult(status -> {
				orderRepository.saveAndFlush(TestRows.order(jdbc, "TEST-DUPLICATE", Order.Type.STORAGE));
				orderRepository.saveAndFlush(TestRows.order(jdbc, "TEST-DUPLICATE", Order.Type.STORAGE));
			});
		}

		@PostMapping("/test/double-booking")
		public void insertDoubleBooking() {
			Instant from = Instant.now().plus(Duration.ofHours(1));
			transactionTemplate.executeWithoutResult(status -> {
				Order first = orderRepository.saveAndFlush(TestRows.order(jdbc, "TEST-BOOKING-1", Order.Type.STORAGE));
				reservationRepository.saveAndFlush(TestRows.storageLeg(jdbc, first, from, from.plus(Duration.ofHours(4))));
				Order second = orderRepository.saveAndFlush(TestRows.order(jdbc, "TEST-BOOKING-2", Order.Type.STORAGE));
				reservationRepository.saveAndFlush(TestRows.storageLeg(jdbc, second, from.plus(Duration.ofHours(1)), from.plus(Duration.ofHours(5))));
			});
		}

		@PostMapping("/test/empty-window")
		public void insertEmptyWindow() {
			Instant from = Instant.now().plus(Duration.ofHours(1));
			transactionTemplate.executeWithoutResult(status -> {
				Order order = orderRepository.saveAndFlush(TestRows.order(jdbc, "TEST-EMPTY-WINDOW", Order.Type.STORAGE));
				reservationRepository.saveAndFlush(TestRows.storageLeg(jdbc, order, from, from));
			});
		}
	}
}
