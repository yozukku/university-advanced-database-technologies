package pl.edu.pk.ztb.bagazomat.customer;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

/** @author Anton Gorokh */
public interface CustomerRepository extends JpaRepository<Customer, Long> {

	boolean existsByKeycloakId(UUID keycloakId);
}
