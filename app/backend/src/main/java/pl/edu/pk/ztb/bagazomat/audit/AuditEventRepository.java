package pl.edu.pk.ztb.bagazomat.audit;

import org.springframework.data.jpa.repository.JpaRepository;

/** @author Anton Gorokh */
public interface AuditEventRepository extends JpaRepository<AuditEvent, Long> {
}
