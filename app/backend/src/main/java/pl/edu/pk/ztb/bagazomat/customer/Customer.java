package pl.edu.pk.ztb.bagazomat.customer;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.SequenceGenerator;
import jakarta.persistence.Table;

import java.util.UUID;

/** @author Anton Gorokh */
@Entity
@Table(name = "customer_")
public class Customer {

	@Id
	@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "customer_id")
	@SequenceGenerator(name = "customer_id", sequenceName = "customer_id_seq_", allocationSize = 1)
	@Column(name = "id_")
	private Long id;

	@Column(name = "keycloak_id_", nullable = false)
	private UUID keycloakId;

	protected Customer() {
	}
}
