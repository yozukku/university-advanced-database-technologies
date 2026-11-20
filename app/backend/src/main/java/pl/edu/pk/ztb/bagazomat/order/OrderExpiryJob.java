package pl.edu.pk.ztb.bagazomat.order;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;
import pl.edu.pk.ztb.bagazomat.audit.AuditActor;
import pl.edu.pk.ztb.bagazomat.audit.AuditChange;
import pl.edu.pk.ztb.bagazomat.audit.AuditEvent;
import pl.edu.pk.ztb.bagazomat.audit.AuditWriter;

/** @author Anton Gorokh */
@Component
class OrderExpiryJob {

	private static final String JOB = "expire-orders";
	private static final String EXPIRED = "EXPIRED";

	private final OrderRepository orderRepository;
	private final ReservationRepository reservationRepository;
	private final AuditWriter auditWriter;
	private final TransactionTemplate transactionTemplate;

	OrderExpiryJob(OrderRepository orderRepository, ReservationRepository reservationRepository, AuditWriter auditWriter,
			TransactionTemplate transactionTemplate) {
		this.orderRepository = orderRepository;
		this.reservationRepository = reservationRepository;
		this.auditWriter = auditWriter;
		this.transactionTemplate = transactionTemplate;
	}

	@Scheduled(cron = "${bagazomat.orders.expiry-cron}")
	void expireOverdueOrders() {
		for (long orderId : orderRepository.findOverdueOrderIds()) {
			transactionTemplate.executeWithoutResult(status -> expire(orderId));
		}
	}

	private void expire(long orderId) {
		orderRepository.lockOrder(orderId);
		if (orderRepository.markExpired(orderId) == 0) {
			return;
		}
		reservationRepository.cancelBookedLegs(orderId);
		auditWriter.write(AuditActor.system(JOB), AuditEvent.EntityType.ORDER, orderId, EXPIRED,
				new AuditChange("status_", Order.Status.AWAITING_PAYMENT.name(), Order.Status.EXPIRED.name()));
	}
}
