package pl.edu.pk.ztb.bagazomat.customer;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.Immutable;

import java.time.Instant;
import java.util.UUID;

/** @author Anton Gorokh */
@Entity
@Immutable
@Table(name = "customer_")
public class Customer {

	@Id
	@Column(name = "id_")
	private Long id;

	@Column(name = "keycloak_id_", nullable = false)
	private UUID keycloakId;

	@Column(name = "phone_", length = 16)
	private String phone;

	@Column(name = "company_name_")
	private String companyName;

	@Column(name = "tax_id_", length = 16)
	private String taxId;

	@Column(name = "billing_address_")
	private String billingAddress;

	@Column(name = "terms_version_", nullable = false, length = 16)
	private String termsVersion;

	@Column(name = "terms_accepted_at_", nullable = false)
	private Instant termsAcceptedAt;

	@Column(name = "created_at_", nullable = false)
	private Instant createdAt;

	protected Customer() {
	}
}
