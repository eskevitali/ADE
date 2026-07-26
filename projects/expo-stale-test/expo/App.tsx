import { StatusBar } from "expo-status-bar";
import { Alert, Pressable, StyleSheet, Text, View } from "react-native";

export default function App() {
  return (
    <View style={styles.container}>
      <View style={styles.phone}>
        <Text style={styles.title}>Stale App</Text>
        <Pressable
          style={styles.button}
          onPress={() => Alert.alert("GPS", "Координаты отправлены")}
        >
          <Text style={styles.buttonText}>Я ТУТ</Text>
        </Pressable>
      </View>
      <StatusBar style="light" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0b0f19",
    alignItems: "center",
    justifyContent: "center",
  },
  phone: {
    width: 320,
    padding: 24,
    borderRadius: 28,
    backgroundColor: "#111827",
    alignItems: "center",
    gap: 20,
  },
  title: {
    color: "#e5e7eb",
    fontSize: 16,
    fontWeight: "600",
  },
  button: {
    width: "100%",
    paddingVertical: 18,
    borderRadius: 16,
    backgroundColor: "#4f46e5",
    alignItems: "center",
  },
  buttonText: {
    color: "#fff",
    fontSize: 22,
    fontWeight: "700",
    letterSpacing: 1,
  },
});
