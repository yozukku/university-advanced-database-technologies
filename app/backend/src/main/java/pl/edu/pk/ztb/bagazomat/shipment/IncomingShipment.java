package pl.edu.pk.ztb.bagazomat.shipment;

import pl.edu.pk.ztb.bagazomat.order.Reservation;

import java.time.Instant;

/** @author Anton Gorokh */
public interface IncomingShipment {

	Long getOrderId();

	Long getReservationId();

	Reservation.Status getStatus();

	String getLockermatName();

	String getLockermatAddress();

	Short getCellNumber();

	Instant getFrom();

	Instant getTo();
}
