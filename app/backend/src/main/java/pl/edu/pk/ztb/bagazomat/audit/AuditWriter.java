package pl.edu.pk.ztb.bagazomat.audit;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

import java.util.List;

/** @author Anton Gorokh */
@Service
public class AuditWriter {

	private final AuditEventRepository auditEventRepository;
	private final JsonMapper jsonMapper;

	public AuditWriter(AuditEventRepository auditEventRepository, JsonMapper jsonMapper) {
		this.auditEventRepository = auditEventRepository;
		this.jsonMapper = jsonMapper;
	}

	@Transactional(propagation = Propagation.MANDATORY)
	public void write(AuditActor actor, AuditEvent.EntityType entityType, long entityId, String action, AuditChange... changes) {
		JsonNode snapshot = jsonMapper.valueToTree(actor);
		JsonNode fieldChanges = jsonMapper.valueToTree(List.of(changes));
		auditEventRepository.save(new AuditEvent(entityType, entityId, action, snapshot, fieldChanges));
	}
}
