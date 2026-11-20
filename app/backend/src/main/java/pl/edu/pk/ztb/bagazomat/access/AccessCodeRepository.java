package pl.edu.pk.ztb.bagazomat.access;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.NativeQuery;

import java.util.List;

/** @author Anton Gorokh */
public interface AccessCodeRepository extends JpaRepository<AccessCode, Long> {

	@NativeQuery("select nextval('access_code_id_seq_')")
	long nextId();

	@NativeQuery("""
			select a.*
			from access_code_ a
			         join reservation_ r on r.id_ = a.reservation_id_
			where r.order_id_ = :orderId and a.status_ = 'ACTIVE'
			order by a.id_
			""")
	List<AccessCode> findActiveByOrderId(long orderId);
}
