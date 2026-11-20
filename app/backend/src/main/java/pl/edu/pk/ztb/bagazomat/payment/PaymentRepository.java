package pl.edu.pk.ztb.bagazomat.payment;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.NativeQuery;

import java.math.BigDecimal;
import java.util.Optional;

/** @author Anton Gorokh */
public interface PaymentRepository extends JpaRepository<Payment, Long> {

	@NativeQuery("""
			select o.price_
			from order_ o
			where o.id_ = :orderId and o.status_ = 'AWAITING_PAYMENT' and o.payment_deadline_ > statement_timestamp()
			  and not exists (select 1 from payment_ p where p.order_id_ = o.id_ and p.kind_ = 'CHARGE' and p.status_ = 'COMPLETED')
			""")
	Optional<BigDecimal> findPayableAmount(long orderId);

	@Modifying
	@NativeQuery("""
			update payment_
			set status_ = 'COMPLETED', provider_ref_ = :providerRef, completed_at_ = statement_timestamp()
			where id_ = :id and status_ = 'PENDING'
			""")
	void complete(long id, String providerRef);

	@Modifying
	@NativeQuery("update payment_ set status_ = 'FAILED' where id_ = :id and status_ = 'PENDING'")
	void fail(long id);
}
