# Language

Shared vocabulary for module boundary audits. Use these terms consistently when describing modules, seams, and leakage.

## Terms

**Module**
Anything with an interface and an implementation. This can be a function, class, package, or larger slice of the system.

**Interface**
Everything a caller must know to use the module correctly. That includes the type signature, invariants, ordering constraints, error behavior, required configuration, and performance expectations.

**Implementation**
What sits behind the interface: the code that actually does the work.

**Depth**
How much behavior a caller can access through a small interface. A deep module gives a lot of leverage through a little surface area. A shallow module exposes almost as much as it hides.

**Seam**
The place where behavior can be changed without editing the existing code in that place. This is where the interface lives.

**Adapter**
A concrete thing that satisfies an interface at a seam.

**Leverage**
What callers gain from a deep module: more capability per unit of interface they need to learn.

**Locality**
What maintainers gain from a deep module: change, bugs, and knowledge stay concentrated instead of spreading across callers.

## Principles

- Depth is a property of the interface, not the implementation.
- The deletion test matters: if removing a module merely relocates complexity, it was not buying much.
- The interface is the test surface.
- One adapter usually means a hypothetical seam; two adapters usually mean a real one.

## Relationships

- A module has one primary interface.
- A seam is where that interface sits.
- An adapter sits on the seam and satisfies the interface.
- Depth creates leverage for callers and locality for maintainers.

## Rejected framings

- Do not use component, service, or API as substitutes for module and interface when you mean the architectural relationship.
- Do not treat interface as only a type declaration or public method list.
- Do not assume every abstraction deserves its own seam.