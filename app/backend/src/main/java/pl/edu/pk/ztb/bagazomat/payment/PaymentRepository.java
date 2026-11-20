package pl.edu.pk.ztb.bagazomat.payment;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.NativeQuery;

import java.math.BigDecimal;
import java.util.List;
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

	@NativeQuery("select nextval('payment_id_seq_')")
	long nextId();

	@NativeQuery("""
			select id_ as id, amount_ as amount
			from payment_
			where order_id_ = :orderId and refundable_id_ is not null
			order by id_
			for update
			""")
	List<Capture> lockCaptures(long orderId);

	@Modifying
	@NativeQuery("""
			insert into payment_ (id_, order_id_, kind_, amount_, provider_, refund_of_id_)
			select :id, p.order_id_, 'REFUND', :amount, p.provider_, p.id_
			from payment_ p
			where p.refundable_id_ = :captureId
			  and :amount > 0
			  and :amount <= p.amount_ - (select coalesce(sum(r.amount_), 0)
			                              from payment_ r
			                              where r.refund_of_id_ = p.id_ and r.status_ in ('PENDING', 'COMPLETED'))
			""")
	int insertRefund(long id, long captureId, BigDecimal amount);

	interface Capture {

		Long getId();

		BigDecimal getAmount();
	}
}
