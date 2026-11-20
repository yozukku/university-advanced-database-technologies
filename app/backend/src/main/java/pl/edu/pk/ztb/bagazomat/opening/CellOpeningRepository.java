package pl.edu.pk.ztb.bagazomat.opening;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.NativeQuery;

/** @author Anton Gorokh */
public interface CellOpeningRepository extends JpaRepository<CellOpening, Long> {

	@NativeQuery("""
			select exists (select 1
			               from cell_opening_ x
			                        join access_code_ a on a.id_ = x.access_code_id_
			                        join reservation_ r on r.id_ = a.reservation_id_
			               where r.order_id_ = :orderId and x.result_ = 'PENDING')
			""")
	boolean hasPendingOpening(long orderId);
}
