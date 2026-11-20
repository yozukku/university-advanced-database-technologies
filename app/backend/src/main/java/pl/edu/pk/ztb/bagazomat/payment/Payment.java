package pl.edu.pk.ztb.bagazomat.payment;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.SequenceGenerator;
import jakarta.persistence.Table;
import org.hibernate.annotations.Generated;

import java.math.BigDecimal;
import java.time.Instant;

/** @author Anton Gorokh */
@Entity
@Table(name = "payment_")
public class Payment {

	@Id
	@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "payment_id")
	@SequenceGenerator(name = "payment_id", sequenceName = "payment_id_seq_", allocationSize = 1)
	@Column(name = "id_")
	private Long id;

	@Column(name = "order_id_", nullable = false)
	private Long orderId;

	@Enumerated(EnumType.STRING)
	@Column(name = "kind_", nullable = false, length = 16)
	private Kind kind;

	@Column(name = "amount_", nullable = false, precision = 10, scale = 2)
	private BigDecimal amount;

	@Enumerated(EnumType.STRING)
	@Column(name = "status_", nullable = false, length = 16)
	private Status status = Status.PENDING;

	@Column(name = "provider_", nullable = false, length = 32)
	private String provider;

	@Column(name = "provider_ref_", length = 128)
	private String providerRef;

	@Column(name = "refund_of_id_")
	private Long refundOfId;

	@Column(name = "incident_id_")
	private Long incidentId;

	@Generated
	@Column(name = "created_at_", nullable = false, updatable = false)
	private Instant createdAt;

	@Column(name = "completed_at_")
	private Instant completedAt;

	protected Payment() {
	}

	public Payment(Long orderId, Kind kind, BigDecimal amount, String provider) {
		this.orderId = orderId;
		this.kind = kind;
		this.amount = amount;
		this.provider = provider;
	}

	public Long getId() {
		return id;
	}

	public enum Kind {
		CHARGE, EXTENSION, OVERSTAY, REFUND, COMPENSATION
	}

	public enum Status {
		PENDING, COMPLETED, FAILED, CANCELLED
	}
}
