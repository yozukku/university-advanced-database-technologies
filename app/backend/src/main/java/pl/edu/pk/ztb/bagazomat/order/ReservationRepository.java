package pl.edu.pk.ztb.bagazomat.order;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

/** @author Anton Gorokh */
public interface ReservationRepository extends JpaRepository<Reservation, Long> {

	Optional<Reservation> findByOrderIdAndStatus(Long orderId, Reservation.Status status);
}
