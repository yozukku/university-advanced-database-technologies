package pl.edu.pk.ztb.bagazomat.order;

import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import pl.edu.pk.ztb.bagazomat.access.AccessCodeRepository;
import pl.edu.pk.ztb.bagazomat.api.ConflictException;
import pl.edu.pk.ztb.bagazomat.api.NotFoundException;
import pl.edu.pk.ztb.bagazomat.audit.AuditActor;
import pl.edu.pk.ztb.bagazomat.audit.AuditChange;
import pl.edu.pk.ztb.bagazomat.audit.AuditEvent;
import pl.edu.pk.ztb.bagazomat.audit.AuditWriter;
import pl.edu.pk.ztb.bagazomat.opening.CellOpeningRepository;
import pl.edu.pk.ztb.bagazomat.payment.RefundService;

import java.math.BigDecimal;
import java.util.UUID;

/** @author Anton Gorokh */
@Service
class OrderCancellationService {

	private static final String CANCELLED = "CANCELLED";
	private static final String DOOR_PENDING = "Skrytka czeka na potwierdzenie otwarcia. Tego zamówienia nie można teraz anulować.";
	private static final String NOT_CANCELLABLE = "Tego zamówienia nie można już anulować.";

	private final OrderRepository orderRepository;
	private final ReservationRepository reservationRepository;
	private final AccessCodeRepository accessCodeRepository;
	private final CellOpeningRepository cellOpeningRepository;
	private final RefundService refundService;
	private final AuditWriter auditWriter;
	private final TransactionTemplate transactionTemplate;

	OrderCancellationService(OrderRepository orderRepository, ReservationRepository reservationRepository, AccessCodeRepository accessCodeRepository,
			CellOpeningRepository cellOpeningRepository, RefundService refundService, AuditWriter auditWriter, TransactionTemplate transactionTemplate) {
		this.orderRepository = orderRepository;
		this.reservationRepository = reservationRepository;
		this.accessCodeRepository = accessCodeRepository;
		this.cellOpeningRepository = cellOpeningRepository;
		this.refundService = refundService;
		this.auditWriter = auditWriter;
		this.transactionTemplate = transactionTemplate;
	}

	CancelledOrder cancel(Jwt jwt, long orderId) {
		return transactionTemplate.execute(status -> cancelOrder(jwt, orderId));
	}

	private CancelledOrder cancelOrder(Jwt jwt, long orderId) {
		Order.Status previous = lockOrder(jwt, orderId);
		rejectPendingOpening(orderId);
		markCancelled(orderId);
		reservationRepository.cancelBookedLegs(orderId);
		accessCodeRepository.revokeActiveCodes(orderId);

		AuditActor actor = AuditActor.customer(jwt);
		auditWriter.write(actor, AuditEvent.EntityType.ORDER, orderId, CANCELLED,
				new AuditChange("status_", previous.name(), Order.Status.CANCELLED.name()));
		BigDecimal refund = refundService.refundCaptures(actor, orderId);
		return new CancelledOrder(orderId, Order.Status.CANCELLED, refund);
	}

	private Order.Status lockOrder(Jwt jwt, long orderId) {
		return orderRepository.lockStorageOrder(UUID.fromString(jwt.getSubject()), orderId)
				.orElseThrow(NotFoundException::new);
	}

	private void rejectPendingOpening(long orderId) {
		if (cellOpeningRepository.hasPendingOpening(orderId)) {
			throw new ConflictException(DOOR_PENDING);
		}
	}

	private void markCancelled(long orderId) {
		if (orderRepository.markCancelled(orderId) == 0) {
			throw new ConflictException(NOT_CANCELLABLE);
		}
	}
}
