<template>
  <div class="layout-shell">
    <slot name="sidebar" />
    <div class="layout-main">
      <slot name="topbar" />
      <main class="content">
        <slot />
      </main>
    </div>
  </div>
</template>
