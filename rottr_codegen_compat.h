#pragma once

// ReXGlue 0.10.0 emits alias attributes before extern "C". GCC silently
// discards those attributes, leaving calls to the guest entry points unresolved.
// Override only the declaration spelling; preserve the original implementation,
// guest context ABI, and weak hook mechanism.
#if defined(__GNUC__) && !defined(__clang__)
#define DEFINE_REX_FUNC(name)                                      \
  extern "C" REX_FUNC(name)                                        \
      __attribute__((alias("__imp__" #name), weak, noinline));     \
  REX_EXTERN(__imp__##name)
#endif
