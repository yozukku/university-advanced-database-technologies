package pl.edu.pk.ztb.bagazomat.access;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.List;
import java.util.stream.LongStream;

/** @author Anton Gorokh */
class AccessCodeHmacTests {

	private static final String PIN_SECRET = "test-pin-secret";
	private static final String CODE_SECRET = "test-code-secret";

	private final AccessCodeHmac accessCodeHmac = new AccessCodeHmac(PIN_SECRET, CODE_SECRET);

	@Test
	void padsLeadingZeroPinToSixDigits() {
		String pin = LongStream.rangeClosed(1, 1_000)
				.mapToObj(accessCodeHmac::pinOf)
				.filter(candidate -> candidate.startsWith("0"))
				.findFirst()
				.orElseThrow();

		Assertions.assertTrue(pin.matches("0[0-9]{5}"), pin);
	}

	@Test
	void derivesSamePinAndHmacAfterRestart() {
		AccessCodeHmac restarted = new AccessCodeHmac(PIN_SECRET, CODE_SECRET);

		for (long id = 1; id <= 100; id++) {
			String pin = accessCodeHmac.pinOf(id);
			Assertions.assertEquals(pin, restarted.pinOf(id));
			Assertions.assertArrayEquals(accessCodeHmac.codeHmacOf(pin), restarted.codeHmacOf(pin));
		}
	}

	@Test
	void keysPinAndHmacWithOwnSecrets() {
		AccessCodeHmac other = new AccessCodeHmac("other-pin-secret", "other-code-secret");

		Assertions.assertNotEquals(pins(accessCodeHmac), pins(other));
		Assertions.assertFalse(Arrays.equals(accessCodeHmac.codeHmacOf("123456"), other.codeHmacOf("123456")));
		Assertions.assertFalse(Arrays.equals(accessCodeHmac.codeHmacOf("123456"), accessCodeHmac.codeHmacOf("123457")));
		Assertions.assertEquals(32, accessCodeHmac.codeHmacOf("123456").length);
	}

	private List<String> pins(AccessCodeHmac hmac) {
		return LongStream.rangeClosed(1, 20)
				.mapToObj(hmac::pinOf)
				.toList();
	}
}
