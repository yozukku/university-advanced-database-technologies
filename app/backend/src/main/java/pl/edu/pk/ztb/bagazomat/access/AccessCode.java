package pl.edu.pk.ztb.bagazomat.access;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.Generated;

import java.time.Instant;

/** @author Anton Gorokh */
@Entity
@Table(name = "access_code_")
public class AccessCode {

	@Id
	@Column(name = "id_")
	private Long id;

	@Column(name = "reservation_id_", nullable = false)
	private Long reservationId;

	@Enumerated(EnumType.STRING)
	@Column(name = "purpose_", nullable = false, length = 16)
	private Purpose purpose;

	@Column(name = "code_hmac_", nullable = false)
	private byte[] codeHmac;

	@Column(name = "sent_to_phone_", length = 16)
	private String sentToPhone;

	@Column(name = "valid_from_", nullable = false)
	private Instant validFrom;

	@Column(name = "valid_to_", nullable = false)
	private Instant validTo;

	@Enumerated(EnumType.STRING)
	@Column(name = "status_", nullable = false, length = 16)
	private Status status = Status.ACTIVE;

	@Generated
	@Column(name = "created_at_", nullable = false, updatable = false)
	private Instant createdAt;

	@Column(name = "used_at_")
	private Instant usedAt;

	protected AccessCode() {
	}

	public AccessCode(Long id, Long reservationId, Purpose purpose, byte[] codeHmac, Instant validFrom, Instant validTo) {
		this.id = id;
		this.reservationId = reservationId;
		this.purpose = purpose;
		this.codeHmac = codeHmac;
		this.validFrom = validFrom;
		this.validTo = validTo;
	}

	public Long getId() {
		return id;
	}

	public enum Purpose {
		DROP_OFF, PICK_UP
	}

	public enum Status {
		ACTIVE, USED, REVOKED
	}
}
