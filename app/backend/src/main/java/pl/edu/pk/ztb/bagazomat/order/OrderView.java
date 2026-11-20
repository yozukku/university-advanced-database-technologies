package pl.edu.pk.ztb.bagazomat.order;

import pl.edu.pk.ztb.bagazomat.lockermat.CellSize;

import java.math.BigDecimal;
import java.time.Instant;

/** @author Anton Gorokh */
public interface OrderView {

	Long getId();

	String getNumber();

	Order.Status getStatus();

	CellSize getSize();

	BigDecimal getPrice();

	Instant getPaymentDeadline();

	Instant getCreatedAt();

	Long getReservationId();

	Reservation.Status getReservationStatus();

	Instant getFrom();

	Instant getTo();

	String getLockermatName();

	String getLockermatAddress();

	Short getCellNumber();
}
