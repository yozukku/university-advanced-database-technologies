package pl.edu.pk.ztb.bagazomat;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import pl.edu.pk.ztb.bagazomat.access.AccessCode;
import pl.edu.pk.ztb.bagazomat.access.AccessCodeRepository;
import pl.edu.pk.ztb.bagazomat.audit.AuditEvent;
import pl.edu.pk.ztb.bagazomat.audit.AuditEventRepository;
import pl.edu.pk.ztb.bagazomat.customer.CustomerRepository;
import pl.edu.pk.ztb.bagazomat.lockermat.LockermatCellRepository;
import pl.edu.pk.ztb.bagazomat.lockermat.LockermatRepository;
import pl.edu.pk.ztb.bagazomat.lockermat.TariffRepository;
import pl.edu.pk.ztb.bagazomat.opening.CellOpening;
import pl.edu.pk.ztb.bagazomat.opening.CellOpeningRepository;
import pl.edu.pk.ztb.bagazomat.order.Order;
import pl.edu.pk.ztb.bagazomat.order.OrderRepository;
import pl.edu.pk.ztb.bagazomat.order.Reservation;
import pl.edu.pk.ztb.bagazomat.order.ReservationRepository;
import pl.edu.pk.ztb.bagazomat.payment.Payment;
import pl.edu.pk.ztb.bagazomat.payment.PaymentRepository;
import pl.edu.pk.ztb.bagazomat.shipment.Shipment;
import pl.edu.pk.ztb.bagazomat.shipment.ShipmentRepository;
import tools.jackson.databind.json.JsonMapper;

import java.math.BigDecimal;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.util.List;

/** @author Anton Gorokh */
@SpringBootTest
@Import(PostgresContainerConfiguration.class)
class EntityMappingTests {

	@Autowired
	private JdbcTemplate jdbc;

	@Autowired
	private LockermatRepository lockermatRepository;

	@Autowired
	private LockermatCellRepository lockermatCellRepository;

	@Autowired
	private TariffRepository tariffRepository;

	@Autowired
	private CustomerRepository customerRepository;

	@Autowired
	private OrderRepository orderRepository;

	@Autowired
	private ReservationRepository reservationRepository;

	@Autowired
	private ShipmentRepository shipmentRepository;

	@Autowired
	private AccessCodeRepository accessCodeRepository;

	@Autowired
	private CellOpeningRepository cellOpeningRepository;

	@Autowired
	private PaymentRepository paymentRepository;

	@Autowired
	private AuditEventRepository auditEventRepository;

	@Test
	void readsSeedThroughReferenceEntities() {
		List<Integer> counts = List.of(lockermatRepository.findAll().size(), lockermatCellRepository.findAll().size(),
				tariffRepository.findAll().size(), customerRepository.findAll().size());

		Assertions.assertEquals(List.of(12, 144, 3, 3), counts);
	}

	@Test
	@Transactional
	void insertsOneRowPerSequenceBackedEntity() {
		Instant from = Instant.now().plus(Duration.ofHours(1));
		Instant to = from.plus(Duration.ofHours(4));

		Order order = orderRepository.saveAndFlush(TestRows.order(jdbc, "TEST-MAP-1", Order.Type.STORAGE));
		assertInserted("order_", orderRepository, order.getId());

		Reservation reservation = reservationRepository.saveAndFlush(TestRows.storageLeg(jdbc, order, from, to));
		assertInserted("reservation_", reservationRepository, reservation.getId());

		Order shipmentOrder = orderRepository.saveAndFlush(TestRows.order(jdbc, "TEST-MAP-2", Order.Type.SHIPMENT));
		Shipment shipment = shipmentRepository.saveAndFlush(new Shipment(shipmentOrder.getId(), "Jan Nowak", "+48500100300", new BigDecimal("100.00")));
		assertInserted("shipment_", shipmentRepository, shipment.getId());

		AccessCode accessCode = accessCodeRepository.saveAndFlush(
				new AccessCode(accessCodeRepository.nextId(), reservation.getId(), AccessCode.Purpose.DROP_OFF, randomDigest(), from, to));
		assertInserted("access_code_", accessCodeRepository, accessCode.getId());

		CellOpening opening = cellOpeningRepository.saveAndFlush(new CellOpening(accessCode.getId(), CellOpening.Channel.APP, TestRows.ANNA));
		assertInserted("cell_opening_", cellOpeningRepository, opening.getId());

		Payment payment = paymentRepository.saveAndFlush(new Payment(order.getId(), Payment.Kind.CHARGE, new BigDecimal("15.00"), "MOCK"));
		assertInserted("payment_", paymentRepository, payment.getId());

		AuditEvent event = auditEventRepository.saveAndFlush(new AuditEvent(AuditEvent.EntityType.ORDER, order.getId(), "CREATED",
				JsonMapper.shared().readTree("{\"kind\": \"SYSTEM\", \"job\": \"test\"}"), JsonMapper.shared().readTree("[]")));
		assertInserted("audit_event_", auditEventRepository, event.getId());
	}

	private void assertInserted(String table, JpaRepository<?, Long> repository, Long id) {
		Assertions.assertTrue(repository.existsById(id), table);
		Assertions.assertEquals(id, jdbc.queryForObject("select currval(?::regclass)", Long.class, table + "id_seq_"), table);
	}

	private byte[] randomDigest() {
		byte[] digest = new byte[32];
		new SecureRandom().nextBytes(digest);
		return digest;
	}
}
