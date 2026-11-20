package pl.edu.pk.ztb.bagazomat.order;

import pl.edu.pk.ztb.bagazomat.audit.AuditActor;
import pl.edu.pk.ztb.bagazomat.audit.AuditEvent;

import java.time.Instant;

/** @author Anton Gorokh */
public interface OrderEvent {

	Long getId();

	Instant getAt();

	AuditEvent.EntityType getEntity();

	String getAction();

	AuditActor.Kind getActorKind();
}
