package pl.edu.pk.ztb.bagazomat.order;

import org.springframework.data.jpa.repository.JpaRepository;

/** @author Anton Gorokh */
public interface ReservationRepository extends JpaRepository<Reservation, Long> {
}
