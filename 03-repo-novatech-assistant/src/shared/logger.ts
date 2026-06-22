// Logger estruturado do projeto. Usa pino quando disponível; caso contrário, um
// fallback estruturado equivalente (mesma interface) para os testes rodarem sem a dep.
// Convenção do projeto: nunca console.log em código de produção — sempre este logger.

type LogFields = Record<string, unknown>;

interface Logger {
  info(fields: LogFields, msg?: string): void;
  warn(fields: LogFields, msg?: string): void;
  error(fields: LogFields, msg?: string): void;
}

function createLogger(): Logger {
  try {
    // import dinâmico evitado em prod; aqui é resolução única no bootstrap do módulo.
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const pino = require("pino");
    return pino({ level: process.env.LOG_LEVEL ?? "info" }) as Logger;
  } catch {
    const emit = (level: string) => (fields: LogFields, msg?: string): void => {
      // saída estruturada em uma linha (stderr), sem console.log de texto solto
      process.stderr.write(JSON.stringify({ level, msg, ...fields, time: Date.now() }) + "\n");
    };
    return { info: emit("info"), warn: emit("warn"), error: emit("error") };
  }
}

export const logger: Logger = createLogger();
