package pl.edu.pk.ztb.bagazomat.opening;

import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import pl.edu.pk.ztb.bagazomat.access.AccessCode;
import pl.edu.pk.ztb.bagazomat.api.ConflictException;
import pl.edu.pk.ztb.bagazomat.api.NotFoundException;
import pl.edu.pk.ztb.bagazomat.audit.AuditActor;
import pl.edu.pk.ztb.bagazomat.audit.AuditChange;
import pl.edu.pk.ztb.bagazomat.audit.AuditEvent;
import pl.edu.pk.ztb.bagazomat.audit.AuditWriter;
import pl.edu.pk.ztb.bagazomat.order.OrderRepository;
import pl.edu.pk.ztb.bagazomat.order.Reservation;

import java.util.UUID;

/** @author Anton Gorokh */
@Service
class OpeningService {

	private static final String DEPOSITED = "DEPOSITED";
	private static final String COLLECTED = "COLLECTED";
	private static final String DOOR_PENDING = "Skrytka czeka na potwierdzenie poprzedniego otwarcia.";
	private static final String NOT_OPENABLE = "Tej skrytki nie można teraz otworzyć.";
	private static final String NOT_CONFIRMED = "Nie udało się potwierdzić otwarcia skrytki.";

	private final OrderRepository orderRepository;
	private final CellOpeningRepository cellOpeningRepository;
	private final SimulatedDoorGateway doorGateway;
	private final AuditWriter auditWriter;
	private final TransactionTemplate transactionTemplate;

	OpeningService(OrderRepository orderRepository, CellOpeningRepository cellOpeningRepository, SimulatedDoorGateway doorGateway, AuditWriter auditWriter,
			TransactionTemplate transactionTemplate) {
		this.orderRepository = orderRepository;
		this.cellOpeningRepository = cellOpeningRepository;
		this.doorGateway = doorGateway;
		this.auditWriter = auditWriter;
		this.transactionTemplate = transactionTemplate;
	}

	OpeningView open(Jwt jwt, long reservationId) {
		PendingOpening opening = transactionTemplate.execute(status -> request(jwt, reservationId));
		CellOpening.Result result = doorGateway.open(opening.id());
		if (result != CellOpening.Result.PENDING) {
			transactionTemplate.executeWithoutResult(status -> recordReply(jwt, opening, result));
		}
		return new OpeningView(opening.id(), opening.purpose(), result);
	}

	private PendingOpening request(Jwt jwt, long reservationId) {
		long orderId = lockOrder(jwt, reservationId);
		rejectPendingOpening(orderId);
		AccessCode.Purpose purpose = purposeOf(cellOpeningRepository.lockCell(reservationId));
		long openingId = insertOpening(jwt, reservationId, purpose);
		return new PendingOpening(openingId, orderId, reservationId, purpose);
	}

	private long lockOrder(Jwt jwt, long reservationId) {
		return orderRepository.lockStorageOrderOfLeg(subjectOf(jwt), reservationId)
				.orElseThrow(NotFoundException::new);
	}

	private void rejectPendingOpening(long orderId) {
		if (cellOpeningRepository.hasPendingOpening(orderId)) {
			throw new ConflictException(DOOR_PENDING);
		}
	}

	private AccessCode.Purpose purposeOf(Reservation.Status legStatus) {
		return switch (legStatus) {
			case BOOKED -> AccessCode.Purpose.DROP_OFF;
			case OCCUPIED -> AccessCode.Purpose.PICK_UP;
			default -> throw new ConflictException(NOT_OPENABLE);
		};
	}

	private long insertOpening(Jwt jwt, long reservationId, AccessCode.Purpose purpose) {
		long openingId = cellOpeningRepository.nextId();
		if (cellOpeningRepository.insertAppOpening(openingId, reservationId, purpose.name(), subjectOf(jwt)) == 0) {
			throw new ConflictException(NOT_OPENABLE);
		}
		return openingId;
	}

	private void recordReply(Jwt jwt, PendingOpening opening, CellOpening.Result result) {
		orderRepository.lockOrder(opening.orderId());
		if (result == CellOpening.Result.DOOR_FAILED) {
			cellOpeningRepository.markDoorFailed(opening.id());
			return;
		}
		confirmOpened(jwt, opening);
	}

	private void confirmOpened(Jwt jwt, PendingOpening opening) {
		if (cellOpeningRepository.markOpened(opening.id()) == 0) {
			throw new ConflictException(NOT_CONFIRMED);
		}
		if (opening.purpose() == AccessCode.Purpose.DROP_OFF) {
			writeLegEvent(jwt, opening, DEPOSITED, Reservation.Status.BOOKED, Reservation.Status.OCCUPIED);
			return;
		}
		writeLegEvent(jwt, opening, COLLECTED, Reservation.Status.OCCUPIED, Reservation.Status.COMPLETED);
		orderRepository.markCompleted(opening.orderId());
	}

	private void writeLegEvent(Jwt jwt, PendingOpening opening, String action, Reservation.Status previous, Reservation.Status next) {
		auditWriter.write(AuditActor.customer(jwt), AuditEvent.EntityType.RESERVATION, opening.reservationId(), action,
				new AuditChange("status_", previous.name(), next.name()));
	}

	private UUID subjectOf(Jwt jwt) {
		return UUID.fromString(jwt.getSubject());
	}
}
