package pl.edu.pk.ztb.bagazomat.opening;

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

import java.time.Instant;
import java.util.UUID;

/** @author Anton Gorokh */
@Entity
@Table(name = "cell_opening_")
public class CellOpening {

	@Id
	@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "cell_opening_id")
	@SequenceGenerator(name = "cell_opening_id", sequenceName = "cell_opening_id_seq_", allocationSize = 1)
	@Column(name = "id_")
	private Long id;

	@Column(name = "access_code_id_")
	private Long accessCodeId;

	@Column(name = "incident_id_")
	private Long incidentId;

	@Enumerated(EnumType.STRING)
	@Column(name = "channel_", nullable = false, length = 16)
	private Channel channel;

	@Column(name = "actor_keycloak_id_")
	private UUID actorKeycloakId;

	@Enumerated(EnumType.STRING)
	@Column(name = "result_", nullable = false, length = 16)
	private Result result = Result.PENDING;

	@Generated
	@Column(name = "requested_at_", nullable = false, updatable = false)
	private Instant requestedAt;

	@Column(name = "closed_at_")
	private Instant closedAt;

	protected CellOpening() {
	}

	public CellOpening(Long accessCodeId, Channel channel, UUID actorKeycloakId) {
		this.accessCodeId = accessCodeId;
		this.channel = channel;
		this.actorKeycloakId = actorKeycloakId;
	}

	public Long getId() {
		return id;
	}

	public enum Channel {
		KEYPAD, APP, SERVICE
	}

	public enum Result {
		PENDING, OPENED, DOOR_FAILED
	}
}
