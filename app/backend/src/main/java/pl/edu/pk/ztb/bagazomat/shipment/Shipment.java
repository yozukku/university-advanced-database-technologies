package pl.edu.pk.ztb.bagazomat.shipment;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.SequenceGenerator;
import jakarta.persistence.Table;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

/** @author Anton Gorokh */
@Entity
@Table(name = "shipment_")
public class Shipment {

	@Id
	@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "shipment_id")
	@SequenceGenerator(name = "shipment_id", sequenceName = "shipment_id_seq_", allocationSize = 1)
	@Column(name = "id_")
	private Long id;

	@Column(name = "order_id_", nullable = false)
	private Long orderId;

	@Column(name = "recipient_name_", nullable = false)
	private String recipientName;

	@Column(name = "recipient_phone_", nullable = false, length = 16)
	private String recipientPhone;

	@Column(name = "declared_value_", nullable = false, precision = 10, scale = 2)
	private BigDecimal declaredValue;

	@Column(name = "courier_keycloak_id_")
	private UUID courierKeycloakId;

	@Column(name = "courier_assigned_at_")
	private Instant courierAssignedAt;

	protected Shipment() {
	}

	public Shipment(Long orderId, String recipientName, String recipientPhone, BigDecimal declaredValue) {
		this.orderId = orderId;
		this.recipientName = recipientName;
		this.recipientPhone = recipientPhone;
		this.declaredValue = declaredValue;
	}

	public Long getId() {
		return id;
	}
}
