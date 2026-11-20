package pl.edu.pk.ztb.bagazomat.payment;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import pl.edu.pk.ztb.bagazomat.api.ConflictException;
import pl.edu.pk.ztb.bagazomat.audit.AuditActor;
import pl.edu.pk.ztb.bagazomat.audit.AuditChange;
import pl.edu.pk.ztb.bagazomat.audit.AuditEvent;
import pl.edu.pk.ztb.bagazomat.audit.AuditWriter;

import java.math.BigDecimal;

/** @author Anton Gorokh */
@Service
public class RefundService {

	private static final BigDecimal NO_REFUND = new BigDecimal("0.00");
	private static final String PROVIDER_REF = "MOCK-%010d";
	private static final String REFUNDED = "REFUNDED";
	private static final String REFUND_REJECTED = "Nie można zwrócić tej płatności.";

	private final PaymentRepository paymentRepository;
	private final AuditWriter auditWriter;

	public RefundService(PaymentRepository paymentRepository, AuditWriter auditWriter) {
		this.paymentRepository = paymentRepository;
		this.auditWriter = auditWriter;
	}

	@Transactional(propagation = Propagation.MANDATORY)
	public BigDecimal refundCaptures(AuditActor actor, long orderId) {
		BigDecimal refunded = NO_REFUND;
		for (PaymentRepository.Capture capture : paymentRepository.lockCaptures(orderId)) {
			refund(actor, capture);
			refunded = refunded.add(capture.getAmount());
		}
		return refunded;
	}

	private void refund(AuditActor actor, PaymentRepository.Capture capture) {
		long refundId = paymentRepository.nextId();
		if (paymentRepository.insertRefund(refundId, capture.getId(), capture.getAmount()) == 0) {
			throw new ConflictException(REFUND_REJECTED);
		}
		paymentRepository.complete(refundId, PROVIDER_REF.formatted(refundId));
		auditWriter.write(actor, AuditEvent.EntityType.PAYMENT, refundId, REFUNDED,
				new AuditChange("status_", null, Payment.Status.COMPLETED.name()));
	}
}
