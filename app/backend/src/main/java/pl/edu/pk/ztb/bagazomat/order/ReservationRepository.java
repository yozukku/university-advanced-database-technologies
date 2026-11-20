package pl.edu.pk.ztb.bagazomat.order;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.NativeQuery;

import java.util.Optional;

/** @author Anton Gorokh */
public interface ReservationRepository extends JpaRepository<Reservation, Long> {

	Optional<Reservation> findByOrderIdAndStatus(Long orderId, Reservation.Status status);

	@Modifying
	@NativeQuery("update reservation_ set status_ = 'CANCELLED' where order_id_ = :orderId and status_ = 'BOOKED'")
	void cancelBookedLegs(long orderId);
}
