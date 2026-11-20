package pl.edu.pk.ztb.bagazomat.opening;

import pl.edu.pk.ztb.bagazomat.access.AccessCode;

/** @author Anton Gorokh */
record PendingOpening(long id, long orderId, long reservationId, AccessCode.Purpose purpose) {
}
