import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

export function AuthScreen({
  onSignIn,
  onRegister,
  onVerify,
}: {
  onSignIn: (email: string, password: string) => Promise<void>;
  onRegister: (email: string, password: string) => Promise<string | null | undefined>;
  onVerify: (token: string) => Promise<void>;
}) {
  const [mode, setMode] = useState<'login' | 'register' | 'verify'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [verificationToken, setVerificationToken] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      if (mode === 'login') await onSignIn(email, password);
      if (mode === 'register') {
        const token = await onRegister(email, password);
        setVerificationToken(token ?? '');
        setMode('verify');
      }
      if (mode === 'verify') {
        await onVerify(verificationToken);
        setMode('login');
        setPassword('');
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Something went wrong');
    } finally {
      setBusy(false);
    }
  };

  const title = mode === 'login' ? 'Welcome back' : mode === 'register' ? 'Create account' : 'Verify email';
  const button = mode === 'login' ? 'Sign in' : mode === 'register' ? 'Create account' : 'Verify email';

  return (
    <View style={styles.container}>
      <Text style={styles.eyebrow}>CONCERTRIP</Text>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.subtitle}>Sign in to discover concerts matched to your taste.</Text>

      {mode !== 'verify' ? (
        <>
          <TextInput value={email} onChangeText={setEmail} placeholder="Email" autoCapitalize="none" keyboardType="email-address" style={styles.input} />
          <TextInput value={password} onChangeText={setPassword} placeholder="Password (8+ characters)" secureTextEntry style={styles.input} />
        </>
      ) : (
        <TextInput value={verificationToken} onChangeText={setVerificationToken} placeholder="Verification token" autoCapitalize="none" style={styles.input} />
      )}

      {error && <Text style={styles.error}>{error}</Text>}
      <Pressable onPress={submit} disabled={busy} style={styles.primaryButton} accessibilityRole="button">
        <Text style={styles.primaryButtonText}>{busy ? 'Please wait...' : button}</Text>
      </Pressable>

      {mode !== 'verify' && (
        <Pressable onPress={() => setMode(mode === 'login' ? 'register' : 'login')} accessibilityRole="button">
          <Text style={styles.switchText}>{mode === 'login' ? 'Create a new account' : 'I already have an account'}</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 24, backgroundColor: '#f6f3ed' },
  eyebrow: { color: '#bd4b2f', fontSize: 12, fontWeight: '800', letterSpacing: 2, marginBottom: 12 },
  title: { color: '#1e2825', fontSize: 32, fontWeight: '800' },
  subtitle: { color: '#67645d', fontSize: 15, lineHeight: 22, marginTop: 10, marginBottom: 24 },
  input: { backgroundColor: '#fffdf8', borderColor: '#ded8cc', borderRadius: 12, borderWidth: 1, color: '#1e2825', marginBottom: 12, paddingHorizontal: 15, paddingVertical: 13 },
  error: { color: '#964238', marginBottom: 12 },
  primaryButton: { backgroundColor: '#bd4b2f', borderRadius: 10, marginBottom: 18, padding: 14 },
  primaryButtonText: { color: '#fffdf8', fontWeight: '800', textAlign: 'center' },
  switchText: { color: '#bd4b2f', fontWeight: '700', textAlign: 'center' },
});
