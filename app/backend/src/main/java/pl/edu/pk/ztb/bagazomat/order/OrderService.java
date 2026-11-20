package pl.edu.pk.ztb.bagazomat.order;

import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import pl.edu.pk.ztb.bagazomat.api.ConflictException;
import pl.edu.pk.ztb.bagazomat.api.InvalidRequestException;
import pl.edu.pk.ztb.bagazomat.api.NotFoundException;
import pl.edu.pk.ztb.bagazomat.audit.AuditActor;
import pl.edu.pk.ztb.bagazomat.audit.AuditChange;
import pl.edu.pk.ztb.bagazomat.audit.AuditEvent;
import pl.edu.pk.ztb.bagazomat.audit.AuditWriter;
import pl.edu.pk.ztb.bagazomat.lockermat.LockermatCellRepository;

import java.sql.SQLException;
import java.util.List;
import java.util.UUID;

/** @author Anton Gorokh */
@Service
class OrderService {

	private static final int MAX_ATTEMPTS = 3;
	private static final String EXCLUSION_VIOLATION = "23P01";
	private static final String CREATED = "CREATED";
	private static final String NO_FREE_CELL = "Brak wolnej skrytki w tym rozmiarze i terminie. Wybierz inny termin lub punkt.";

	private final OrderRepository orderRepository;
	private final ReservationRepository reservationRepository;
	private final LockermatCellRepository lockermatCellRepository;
	private final AuditWriter auditWriter;
	private final TransactionTemplate transactionTemplate;

	OrderService(OrderRepository orderRepository, ReservationRepository reservationRepository, LockermatCellRepository lockermatCellRepository,
			AuditWriter auditWriter, TransactionTemplate transactionTemplate) {
		this.orderRepository = orderRepository;
		this.reservationRepository = reservationRepository;
		this.lockermatCellRepository = lockermatCellRepository;
		this.auditWriter = auditWriter;
		this.transactionTemplate = transactionTemplate;
	}

	OrderView create(Jwt jwt, NewOrder request) {
		validate(request);
		long orderId = bookWithRetry(jwt, request);
		return find(jwt, orderId);
	}

	List<OrderView> findAll(Jwt jwt) {
		return orderRepository.findStorageOrders(subjectOf(jwt));
	}

	OrderView find(Jwt jwt, long id) {
		return orderRepository.findStorageOrder(subjectOf(jwt), id)
				.orElseThrow(NotFoundException::new);
	}

	private void validate(NewOrder request) {
		if (request.lockermatId() == null || request.size() == null || request.from() == null || request.to() == null
				|| !request.from().isBefore(request.to())) {
			throw new InvalidRequestException();
		}
	}

	private long bookWithRetry(Jwt jwt, NewOrder request) {
		for (int attempt = 1; ; attempt++) {
			try {
				return transactionTemplate.execute(status -> book(jwt, request));
			} catch (DataIntegrityViolationException exception) {
				if (attempt == MAX_ATTEMPTS || !isExclusionViolation(exception)) {
					throw exception;
				}
			}
		}
	}

	private long book(Jwt jwt, NewOrder request) {
		long orderId = insertOrder(jwt, request);
		long cellId = pickCell(request);
		reservationRepository.saveAndFlush(new Reservation(orderId, request.size(), cellId, Reservation.Leg.STORAGE, request.from(), request.to()));
		auditWriter.write(AuditActor.customer(jwt), AuditEvent.EntityType.ORDER, orderId, CREATED,
				new AuditChange("status_", null, Order.Status.AWAITING_PAYMENT.name()));
		return orderId;
	}

	private long insertOrder(Jwt jwt, NewOrder request) {
		long orderId = orderRepository.nextId();
		String number = "BAG-%010d".formatted(orderId);
		int inserted = orderRepository.insertStorageOrder(orderId, number, subjectOf(jwt), request.size().name(), request.from(), request.to());
		if (inserted == 0) {
			throw new InvalidRequestException();
		}
		return orderId;
	}

	private long pickCell(NewOrder request) {
		return lockermatCellRepository.findFreeCell(request.lockermatId(), request.size().name(), request.from(), request.to())
				.orElseThrow(() -> new ConflictException(NO_FREE_CELL));
	}

	private boolean isExclusionViolation(Throwable exception) {
		for (Throwable cause = exception; cause != null; cause = cause.getCause()) {
			if (cause instanceof SQLException sqlException && EXCLUSION_VIOLATION.equals(sqlException.getSQLState())) {
				return true;
			}
		}
		return false;
	}

	private UUID subjectOf(Jwt jwt) {
		return UUID.fromString(jwt.getSubject());
	}
}
