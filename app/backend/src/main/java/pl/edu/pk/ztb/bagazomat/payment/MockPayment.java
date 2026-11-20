package pl.edu.pk.ztb.bagazomat.payment;

/** @author Anton Gorokh */
record MockPayment(Result result) {

	enum Result {
		SUCCESS, FAILURE
	}
}
