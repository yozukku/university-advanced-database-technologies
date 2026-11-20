package pl.edu.pk.ztb.bagazomat.payment;

import java.math.BigDecimal;

/** @author Anton Gorokh */
record PaymentView(Long id, Payment.Status status, BigDecimal amount) {
}
