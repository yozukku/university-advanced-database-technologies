package pl.edu.pk.ztb.bagazomat.order;

import java.math.BigDecimal;

/** @author Anton Gorokh */
record CancelledOrder(Long id, Order.Status status, BigDecimal refund) {
}
