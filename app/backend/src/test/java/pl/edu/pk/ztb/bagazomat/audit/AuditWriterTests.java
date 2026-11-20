package pl.edu.pk.ztb.bagazomat.audit;

import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.transaction.IllegalTransactionStateException;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionTemplate;
import pl.edu.pk.ztb.bagazomat.PostgresContainerConfiguration;
import pl.edu.pk.ztb.bagazomat.TestRows;
import pl.edu.pk.ztb.bagazomat.order.Order;
import pl.edu.pk.ztb.bagazomat.order.OrderRepository;
import pl.edu.pk.ztb.bagazomat.order.ReservationRepository;

import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.atomic.AtomicLong;

/** @author Anton Gorokh */
@SpringBootTest
@Import(PostgresContainerConfiguration.class)
class AuditWriterTests {

	private static final Jwt ANNA = token(TestRows.ANNA.toString(), "anna@example.test");
	private static final Jwt JAN = token("a4bba234-ddf1-5dbc-bf7d-fca171bfe08f", "jan@example.test");

	@Autowired
	private AuditWriter auditWriter;

	@Autowired
	private OrderRepository orderRepository;

	@Autowired
	private ReservationRepository reservationRepository;

	@Autowired
	private TransactionTemplate transactionTemplate;

	@Autowired
	private EntityManager entityManager;

	@Autowired
	private JdbcTemplate jdbc;

	@Test
	@Transactional
	void writesActorSnapshotAndChanges() {
		auditWriter.write(AuditActor.customer(ANNA), AuditEvent.EntityType.ORDER, -1, "CREATED",
				new AuditChange("status_", null, "AWAITING_PAYMENT"));
		auditWriter.write(AuditActor.recipient(JAN, "+48500100300"), AuditEvent.EntityType.RESERVATION, -2, "COLLECTED",
				new AuditChange("status_", "OCCUPIED", "COMPLETED"));
		auditWriter.write(AuditActor.system("expire-orders"), AuditEvent.EntityType.ORDER, -3, "EXPIRED",
				new AuditChange("status_", "AWAITING_PAYMENT", "EXPIRED"), new AuditChange("closed_at_", null, "2026-11-20T10:15:00Z"));
		entityManager.flush();

		assertEvent("ORDER", -1, "CREATED",
				"{\"kind\": \"CUSTOMER\", \"keycloak_id\": \"900f9895-3b4d-5e82-a35f-ad11c64f9f00\", \"email\": \"anna@example.test\"}",
				"[{\"f\": \"status_\", \"old\": null, \"new\": \"AWAITING_PAYMENT\"}]");
		assertEvent("RESERVATION", -2, "COLLECTED",
				"{\"kind\": \"RECIPIENT\", \"keycloak_id\": \"a4bba234-ddf1-5dbc-bf7d-fca171bfe08f\", \"email\": \"jan@example.test\", \"phone\": \"+48500100300\"}",
				"[{\"f\": \"status_\", \"old\": \"OCCUPIED\", \"new\": \"COMPLETED\"}]");
		assertEvent("ORDER", -3, "EXPIRED",
				"{\"kind\": \"SYSTEM\", \"job\": \"expire-orders\"}",
				"[{\"f\": \"status_\", \"old\": \"AWAITING_PAYMENT\", \"new\": \"EXPIRED\"}, {\"f\": \"closed_at_\", \"old\": null, \"new\": \"2026-11-20T10:15:00Z\"}]");
	}

	@Test
	void rollsBackAuditEventWhenBusinessWriteFails() {
		AtomicLong orderId = new AtomicLong();

		Assertions.assertThrows(DataIntegrityViolationException.class, () -> transactionTemplate.executeWithoutResult(status -> {
			Order order = orderRepository.saveAndFlush(TestRows.order(jdbc, "TEST-AUDIT-ROLLBACK", Order.Type.STORAGE));
			orderId.set(order.getId());
			auditWriter.write(AuditActor.customer(ANNA), AuditEvent.EntityType.ORDER, order.getId(), "CREATED",
					new AuditChange("status_", null, "AWAITING_PAYMENT"));
			entityManager.flush();
			Assertions.assertEquals(1, countEvents(order.getId()));

			Instant from = Instant.now().plus(Duration.ofHours(1));
			reservationRepository.saveAndFlush(TestRows.storageLeg(jdbc, order, from, from));
		}));

		Assertions.assertEquals(0, countEvents(orderId.get()));
		Assertions.assertEquals(0, jdbc.queryForObject("select count(*) from order_ where id_ = ?", Integer.class, orderId.get()));
	}

	@Test
	void refusesToWriteOutsideTransaction() {
		Assertions.assertThrows(IllegalTransactionStateException.class,
				() -> auditWriter.write(AuditActor.system("test"), AuditEvent.EntityType.ORDER, -1, "CREATED"));
	}

	private void assertEvent(String entity, long entityId, String action, String actor, String changes) {
		Assertions.assertEquals(1, jdbc.queryForObject("""
				select count(*)
				from audit_event_
				where entity_ = ? and entity_id_ = ? and action_ = ? and actor_ = ?::jsonb and changes_ = ?::jsonb
				""", Integer.class, entity, entityId, action, actor, changes), action);
	}

	private int countEvents(long orderId) {
		return jdbc.queryForObject("select count(*) from audit_event_ where entity_ = 'ORDER' and entity_id_ = ?", Integer.class, orderId);
	}

	private static Jwt token(String subject, String email) {
		return Jwt.withTokenValue("test").header("alg", "none").subject(subject).claim("email", email).build();
	}
}
