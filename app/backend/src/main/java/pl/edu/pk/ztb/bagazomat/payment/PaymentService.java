package pl.edu.pk.ztb.bagazomat.payment;

import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import pl.edu.pk.ztb.bagazomat.access.AccessCodeService;
import pl.edu.pk.ztb.bagazomat.api.ConflictException;
import pl.edu.pk.ztb.bagazomat.api.InvalidRequestException;
import pl.edu.pk.ztb.bagazomat.api.NotFoundException;
import pl.edu.pk.ztb.bagazomat.audit.AuditActor;
import pl.edu.pk.ztb.bagazomat.audit.AuditChange;
import pl.edu.pk.ztb.bagazomat.audit.AuditEvent;
import pl.edu.pk.ztb.bagazomat.audit.AuditWriter;
import pl.edu.pk.ztb.bagazomat.order.Order;
import pl.edu.pk.ztb.bagazomat.order.OrderRepository;

import java.math.BigDecimal;
import java.sql.SQLException;
import java.util.UUID;

/** @author Anton Gorokh */
@Service
class PaymentService {

	private static final int MAX_ATTEMPTS = 3;
	private static final String EXCLUSION_VIOLATION = "23P01";
	private static final String HMAC_WINDOW_EXCLUSION = "access_code_hmac_window__ex";
	private static final String PROVIDER = "MOCK";
	private static final String PAID = "PAID";
	private static final String NOT_PAYABLE = "Tego zamówienia nie można już opłacić.";

	private final PaymentRepository paymentRepository;
	private final OrderRepository orderRepository;
	private final AccessCodeService accessCodeService;
	private final AuditWriter auditWriter;
	private final TransactionTemplate transactionTemplate;

	PaymentService(PaymentRepository paymentRepository, OrderRepository orderRepository, AccessCodeService accessCodeService, AuditWriter auditWriter,
			TransactionTemplate transactionTemplate) {
		this.paymentRepository = paymentRepository;
		this.orderRepository = orderRepository;
		this.accessCodeService = accessCodeService;
		this.auditWriter = auditWriter;
		this.transactionTemplate = transactionTemplate;
	}

	PaymentView pay(Jwt jwt, long orderId, MockPayment request) {
		if (request.result() == null) {
			throw new InvalidRequestException();
		}
		return payWithRetry(jwt, orderId, request.result());
	}

	private PaymentView payWithRetry(Jwt jwt, long orderId, MockPayment.Result result) {
		for (int attempt = 1; ; attempt++) {
			try {
				return transactionTemplate.execute(status -> settle(jwt, orderId, result));
			} catch (DataIntegrityViolationException exception) {
				if (attempt == MAX_ATTEMPTS || !isHmacCollision(exception)) {
					throw exception;
				}
			}
		}
	}

	private PaymentView settle(Jwt jwt, long orderId, MockPayment.Result result) {
		lockOrder(jwt, orderId);
		BigDecimal amount = payableAmount(orderId);
		long chargeId = paymentRepository.saveAndFlush(new Payment(orderId, Payment.Kind.CHARGE, amount, PROVIDER)).getId();
		if (result == MockPayment.Result.FAILURE) {
			paymentRepository.fail(chargeId);
			return new PaymentView(chargeId, Payment.Status.FAILED, amount);
		}
		capture(jwt, orderId, chargeId);
		return new PaymentView(chargeId, Payment.Status.COMPLETED, amount);
	}

	private void lockOrder(Jwt jwt, long orderId) {
		if (orderRepository.lockStorageOrder(UUID.fromString(jwt.getSubject()), orderId).isEmpty()) {
			throw new NotFoundException();
		}
	}

	private BigDecimal payableAmount(long orderId) {
		return paymentRepository.findPayableAmount(orderId)
				.orElseThrow(() -> new ConflictException(NOT_PAYABLE));
	}

	private void capture(Jwt jwt, long orderId, long chargeId) {
		paymentRepository.complete(chargeId, "%s-%010d".formatted(PROVIDER, chargeId));
		orderRepository.markPaid(orderId);
		accessCodeService.issueStorageCodes(orderId);
		auditWriter.write(AuditActor.customer(jwt), AuditEvent.EntityType.ORDER, orderId, PAID,
				new AuditChange("status_", Order.Status.AWAITING_PAYMENT.name(), Order.Status.PAID.name()));
	}

	private boolean isHmacCollision(Throwable exception) {
		for (Throwable cause = exception; cause != null; cause = cause.getCause()) {
			if (cause instanceof SQLException sqlException && EXCLUSION_VIOLATION.equals(sqlException.getSQLState())
					&& sqlException.getMessage().contains(HMAC_WINDOW_EXCLUSION)) {
				return true;
			}
		}
		return false;
	}
}
