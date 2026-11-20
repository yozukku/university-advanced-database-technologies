package pl.edu.pk.ztb.bagazomat.audit;

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
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
import tools.jackson.databind.JsonNode;

import java.time.Instant;

/** @author Anton Gorokh */
@Entity
@Table(name = "audit_event_")
public class AuditEvent {

	@Id
	@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "audit_event_id")
	@SequenceGenerator(name = "audit_event_id", sequenceName = "audit_event_id_seq_", allocationSize = 1)
	@Column(name = "id_")
	private Long id;

	@Generated
	@Column(name = "at_", nullable = false, updatable = false)
	private Instant at;

	@Enumerated(EnumType.STRING)
	@Column(name = "entity_", nullable = false, length = 24)
	private EntityType entityType;

	@Column(name = "entity_id_", nullable = false)
	private Long entityId;

	@Column(name = "action_", nullable = false, length = 32)
	private String action;

	@JdbcTypeCode(SqlTypes.JSON)
	@Column(name = "actor_", nullable = false)
	private JsonNode actor;

	@JdbcTypeCode(SqlTypes.JSON)
	@Column(name = "changes_")
	private JsonNode changes;

	protected AuditEvent() {
	}

	public AuditEvent(EntityType entityType, Long entityId, String action, JsonNode actor, JsonNode changes) {
		this.entityType = entityType;
		this.entityId = entityId;
		this.action = action;
		this.actor = actor;
		this.changes = changes;
	}

	public Long getId() {
		return id;
	}

	public enum EntityType {
		ORDER, RESERVATION, PAYMENT
	}
}
