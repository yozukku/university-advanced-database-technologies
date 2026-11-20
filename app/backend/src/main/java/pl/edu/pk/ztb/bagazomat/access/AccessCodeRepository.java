package pl.edu.pk.ztb.bagazomat.access;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.NativeQuery;

/** @author Anton Gorokh */
public interface AccessCodeRepository extends JpaRepository<AccessCode, Long> {

	@NativeQuery("select nextval('access_code_id_seq_')")
	long nextId();
}
