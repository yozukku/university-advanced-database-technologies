package pl.edu.pk.ztb.bagazomat.access;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

/** @author Anton Gorokh */
@Component
public class AccessCodeHmac {

	private static final String ALGORITHM = "HmacSHA256";
	private static final BigInteger PIN_RANGE = BigInteger.valueOf(1_000_000);

	private final SecretKeySpec pinKey;
	private final SecretKeySpec codeKey;

	public AccessCodeHmac(@Value("${bagazomat.access.pin-secret}") String pinSecret, @Value("${bagazomat.access.code-secret}") String codeSecret) {
		this.pinKey = new SecretKeySpec(pinSecret.getBytes(StandardCharsets.UTF_8), ALGORITHM);
		this.codeKey = new SecretKeySpec(codeSecret.getBytes(StandardCharsets.UTF_8), ALGORITHM);
	}

	public String pinOf(long codeId) {
		BigInteger digest = new BigInteger(1, sign(pinKey, "pin:" + codeId));
		return "%06d".formatted(digest.mod(PIN_RANGE).intValue());
	}

	public byte[] codeHmacOf(String pin) {
		return sign(codeKey, "code:" + pin);
	}

	private byte[] sign(SecretKeySpec key, String message) {
		try {
			Mac mac = Mac.getInstance(ALGORITHM);
			mac.init(key);
			return mac.doFinal(message.getBytes(StandardCharsets.UTF_8));
		} catch (GeneralSecurityException exception) {
			throw new IllegalStateException(exception);
		}
	}
}
