import { computed, ref } from 'vue'
import { ApiError, completeMockPayment, createCheckout, fetchMembership } from '../api'
import type { CheckoutResponse, MembershipState } from '../types'
import { useAuth } from './useAuth'

const EMPTY: MembershipState = {
  active: false,
  plan: '',
  starts_at: '',
  expires_at: '',
  expires_text: '',
}

const membership = ref<MembershipState>({ ...EMPTY })
const checkingOut = ref(false)
const error = ref('')
const checkout = ref<CheckoutResponse | null>(null)
const showMockPay = ref(false)

const isPro = computed(() => membership.value.active)

async function load() {
  const { token, isLoggedIn } = useAuth()
  if (!isLoggedIn.value) {
    membership.value = { ...EMPTY }
    return
  }
  try {
    membership.value = await fetchMembership(token.value)
  } catch {
    // 拉取会员状态失败静默，下次进入再试
  }
}

async function purchase(): Promise<boolean> {
  const { token, isLoggedIn, openAuth } = useAuth()
  if (!isLoggedIn.value) {
    openAuth()
    return false
  }
  checkingOut.value = true
  error.value = ''
  try {
    const res = await createCheckout(token.value)
    checkout.value = res
    if (res.mode === 'mock') {
      showMockPay.value = true
    } else {
      window.location.href = res.checkout_url
    }
    return true
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : '创建支付订单失败，请稍后重试'
    return false
  } finally {
    checkingOut.value = false
  }
}

async function confirmMockPay(): Promise<boolean> {
  const { token } = useAuth()
  error.value = ''
  try {
    membership.value = await completeMockPayment(token.value)
    showMockPay.value = false
    checkout.value = null
    return true
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : '模拟支付失败，请稍后重试'
    return false
  }
}

function cancelMockPay() {
  showMockPay.value = false
  checkout.value = null
}

export function useMembership() {
  return {
    membership,
    isPro,
    checkingOut,
    error,
    showMockPay,
    load,
    purchase,
    confirmMockPay,
    cancelMockPay,
  }
}
