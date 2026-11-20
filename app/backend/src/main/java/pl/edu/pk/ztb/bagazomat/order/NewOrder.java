package pl.edu.pk.ztb.bagazomat.order;

import pl.edu.pk.ztb.bagazomat.lockermat.CellSize;

import java.time.Instant;

/** @author Anton Gorokh */
record NewOrder(Long lockermatId, CellSize size, Instant from, Instant to) {
}
