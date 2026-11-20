package pl.edu.pk.ztb.bagazomat.payment;

import org.springframework.data.jpa.repository.JpaRepository;

/** @author Anton Gorokh */
public interface PaymentRepository extends JpaRepository<Payment, Long> {
}
