package pl.edu.pk.ztb.bagazomat.demo;

import org.springframework.context.annotation.Profile;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import pl.edu.pk.ztb.bagazomat.access.AccessCodeService;
import pl.edu.pk.ztb.bagazomat.api.ConflictException;
import pl.edu.pk.ztb.bagazomat.audit.AuditActor;
import pl.edu.pk.ztb.bagazomat.audit.AuditChange;
import pl.edu.pk.ztb.bagazomat.audit.AuditEvent;
import pl.edu.pk.ztb.bagazomat.audit.AuditWriter;
import pl.edu.pk.ztb.bagazomat.customer.CustomerRepository;
import pl.edu.pk.ztb.bagazomat.lockermat.CellSize;
import pl.edu.pk.ztb.bagazomat.order.Order;
import pl.edu.pk.ztb.bagazomat.order.OrderRepository;
import pl.edu.pk.ztb.bagazomat.order.Reservation;
import pl.edu.pk.ztb.bagazomat.shipment.IncomingShipment;
import pl.edu.pk.ztb.bagazomat.shipment.Shipment;
import pl.edu.pk.ztb.bagazomat.shipment.ShipmentRepository;
import pl.edu.pk.ztb.bagazomat.shipment.ShipmentService;

import java.math.BigDecimal;
import java.sql.SQLException;
import java.time.Duration;
import java.time.Instant;
import java.util.UUID;

/** @author Anton Gorokh */
@Service
@Profile("dev")
class ShipmentSimulator {

	private static final int MAX_ATTEMPTS = 3;
	private static final String EXCLUSION_VIOLATION = "23P01";
	private static final UUID DEMO_SENDER = UUID.fromString("95912bb7-ca81-5398-b494-078466a4edd2");
	private static final Duration ORIGIN_DEPOSITED_AGO = Duration.ofDays(1).plusMinutes(1);
	private static final Duration ORIGIN_COLLECTED_AGO = Duration.ofDays(1);
	private static final Duration PICK_UP_WINDOW = Duration.ofDays(3);
	private static final AuditActor SIMULATOR = AuditActor.system("simulate-shipment");
	private static final String CREATED = "CREATED";
	private static final String PAID = "PAID";
	private static final String DEPOSITED = "DEPOSITED";
	private static final String COLLECTED = "COLLECTED";
	private static final String NO_PHONE = "Konto nie ma numeru telefonu, więc nie może odebrać przesyłki.";
	private static final String NO_FREE_CELL = "Brak wolnej skrytki na przesyłkę. Spróbuj ponownie później.";
	private static final String NO_TARIFF = "Brak aktualnej taryfy dla przesyłki.";

	private final ShipmentSimulationRepository simulationRepository;
	private final OrderRepository orderRepository;
	private final ShipmentRepository shipmentRepository;
	private final CustomerRepository customerRepository;
	private final AccessCodeService accessCodeService;
	private final ShipmentService shipmentService;
	private final AuditWriter auditWriter;
	private final TransactionTemplate transactionTemplate;

	ShipmentSimulator(ShipmentSimulationRepository simulationRepository, OrderRepository orderRepository, ShipmentRepository shipmentRepository,
			CustomerRepository customerRepository, AccessCodeService accessCodeService, ShipmentService shipmentService, AuditWriter auditWriter,
			TransactionTemplate transactionTemplate) {
		this.simulationRepository = simulationRepository;
		this.orderRepository = orderRepository;
		this.shipmentRepository = shipmentRepository;
		this.customerRepository = customerRepository;
		this.accessCodeService = accessCodeService;
		this.shipmentService = shipmentService;
		this.auditWriter = auditWriter;
		this.transactionTemplate = transactionTemplate;
	}

	IncomingShipment simulate(Jwt jwt) {
		String phone = phoneOf(jwt);
		long orderId = simulateWithRetry(jwt, phone);
		return shipmentService.findIncoming(jwt, orderId);
	}

	private String phoneOf(Jwt jwt) {
		return customerRepository.findPhone(UUID.fromString(jwt.getSubject()))
				.orElseThrow(() -> new ConflictException(NO_PHONE));
	}

	private long simulateWithRetry(Jwt jwt, String phone) {
		for (int attempt = 1; ; attempt++) {
			try {
				return transactionTemplate.execute(status -> fabricate(jwt, phone));
			} catch (DataIntegrityViolationException exception) {
				if (attempt == MAX_ATTEMPTS || !isExclusionViolation(exception)) {
					throw exception;
				}
			}
		}
	}

	private long fabricate(Jwt jwt, String phone) {
		Instant now = simulationRepository.now();
		ShipmentSimulationRepository.FreeCell destination = pickDestination(now);
		long originCellId = pickOrigin(destination, now);
		long orderId = insertOrder(destination.getSize());
		shipmentRepository.saveAndFlush(new Shipment(orderId, jwt.getClaimAsString("name"), phone, BigDecimal.ZERO));
		long originId = insertOrigin(orderId, originCellId, now);
		long destinationId = insertDestination(orderId, destination.getCellId(), now);
		accessCodeService.issueRecipientPickUpCode(destinationId, phone);
		writeHistory(orderId, originId, destinationId);
		return orderId;
	}

	private ShipmentSimulationRepository.FreeCell pickDestination(Instant now) {
		return simulationRepository.findDestinationCell(now, now.plus(PICK_UP_WINDOW))
				.orElseThrow(() -> new ConflictException(NO_FREE_CELL));
	}

	private long pickOrigin(ShipmentSimulationRepository.FreeCell destination, Instant now) {
		String size = destination.getSize().name();
		return simulationRepository.findOriginCell(destination.getLockermatId(), size, now.minus(ORIGIN_DEPOSITED_AGO), now.minus(ORIGIN_COLLECTED_AGO))
				.orElseThrow(() -> new ConflictException(NO_FREE_CELL));
	}

	private long insertOrder(CellSize size) {
		long orderId = orderRepository.nextId();
		if (simulationRepository.insertPaidOrder(orderId, "BAG-%010d".formatted(orderId), DEMO_SENDER, size.name()) == 0) {
			throw new ConflictException(NO_TARIFF);
		}
		return orderId;
	}

	private long insertOrigin(long orderId, long cellId, Instant now) {
		long originId = simulationRepository.nextReservationId();
		simulationRepository.insertCollectedOrigin(originId, orderId, cellId, now.minus(ORIGIN_DEPOSITED_AGO), now.minus(ORIGIN_COLLECTED_AGO));
		return originId;
	}

	private long insertDestination(long orderId, long cellId, Instant now) {
		long destinationId = simulationRepository.nextReservationId();
		simulationRepository.insertOccupiedDestination(destinationId, orderId, cellId, now, now.plus(PICK_UP_WINDOW));
		return destinationId;
	}

	private void writeHistory(long orderId, long originId, long destinationId) {
		writeStatusEvent(AuditEvent.EntityType.ORDER, orderId, CREATED, null, Order.Status.AWAITING_PAYMENT);
		writeStatusEvent(AuditEvent.EntityType.ORDER, orderId, PAID, Order.Status.AWAITING_PAYMENT, Order.Status.PAID);
		writeStatusEvent(AuditEvent.EntityType.RESERVATION, originId, DEPOSITED, Reservation.Status.BOOKED, Reservation.Status.OCCUPIED);
		writeStatusEvent(AuditEvent.EntityType.RESERVATION, originId, COLLECTED, Reservation.Status.OCCUPIED, Reservation.Status.COMPLETED);
		writeStatusEvent(AuditEvent.EntityType.RESERVATION, destinationId, DEPOSITED, Reservation.Status.BOOKED, Reservation.Status.OCCUPIED);
	}

	private void writeStatusEvent(AuditEvent.EntityType entityType, long entityId, String action, Enum<?> previous, Enum<?> next) {
		String previousName = previous == null ? null : previous.name();
		auditWriter.write(SIMULATOR, entityType, entityId, action, new AuditChange("status_", previousName, next.name()));
	}

	private boolean isExclusionViolation(Throwable exception) {
		for (Throwable cause = exception; cause != null; cause = cause.getCause()) {
			if (cause instanceof SQLException sqlException && EXCLUSION_VIOLATION.equals(sqlException.getSQLState())) {
				return true;
			}
		}
		return false;
	}
}
