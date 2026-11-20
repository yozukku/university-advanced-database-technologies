package pl.edu.pk.ztb.bagazomat.customer;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.NativeQuery;

import java.util.Optional;
import java.util.UUID;

/** @author Anton Gorokh */
public interface CustomerRepository extends JpaRepository<Customer, Long> {

	boolean existsByKeycloakId(UUID keycloakId);

	@NativeQuery("select phone_ from customer_ where keycloak_id_ = :keycloakId")
	Optional<String> findPhone(UUID keycloakId);
}
