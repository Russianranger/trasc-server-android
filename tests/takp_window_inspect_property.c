/* Serialization predicates/escaping must diagnose the guards without accepting
 * a changed property representation as a camera repair. No X server needed. */
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#define main inspector_program_main
#include "../native/presentation/takp-window-inspect.c"
#undef main

int main(void) {
    struct property name = {.status = Success, .type = XA_STRING, .format = 8, .count = 8, .bytes = 8};
    memcpy(name.value, "EqW-TAKP", 8);
    assert(title_match(&name, 0) && !title_match(&name, 1));
    name.bytes++; name.count++;
    assert(!title_match(&name, 0) && title_match(&name, 1));
    name.after = 1;
    assert(!title_match(&name, 0) && !title_match(&name, 1));
    name.after = 0; name.format = 32;
    assert(!title_match(&name, 1));
    struct property klass = {.status = Success, .type = XA_STRING, .format = 8, .count = 22, .bytes = 22};
    memcpy(klass.value, "eqgame.exe\0eqgame.exe\0", 22);
    assert(class_match(&klass, 0) && !class_match(&klass, 1) && eqgame_class_field(&klass));
    klass.bytes++; klass.count++;
    assert(!class_match(&klass, 0) && class_match(&klass, 1) && eqgame_class_field(&klass));
    klass.type = 999; /* Wrong atom type still retains diagnostic byte identity. */
    assert(class_match(&klass, 1));
    klass.bytes = 21;
    assert(!class_match(&klass, 0) && !class_match(&klass, 1));
    klass.bytes = 10;
    assert(eqgame_class_field(&klass));
    klass.bytes = 9;
    assert(!eqgame_class_field(&klass));
    char escaped[64];
    const unsigned char bytes[] = {'a', 0, '"', '\\', '\n', 255};
    quote_bytes(escaped, sizeof(escaped), bytes, sizeof(bytes));
    assert(!strcmp(escaped, "a\\u0000\\u0022\\u005c\\u000a\\u00ff"));
    char small[4];
    quote_bytes(small, sizeof(small), bytes, sizeof(bytes));
    assert(!strcmp(small, "a"));
    char full[INSPECT_PROPERTY_BYTES * 6u + 1u];
    unsigned char controls[INSPECT_PROPERTY_BYTES] = {0};
    quote_bytes(full, sizeof(full), controls, sizeof(controls));
    assert(strlen(full) == INSPECT_PROPERTY_BYTES * 6u);
    puts("PASS: exact/optional-NUL property identity, changed format/type, embedded NUL and bounded JSON bytes");
    return 0;
}
