/**
 * Next.js middleware — route protection.
 *
 * Unauthenticated users are redirected to /login.
 * /login and /signup are always accessible.
 *
 * NOTE: The real auth check happens inside each page via useAuth().
 * The middleware provides a fast redirect for users without a session
 * cookie, protecting against flashes of protected content.
 */
import { NextRequest, NextResponse } from 'next/server'

const PUBLIC_PATHS = ['/login', '/signup']

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Allow public paths
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next()
  }

  // Allow root / (home page — existing lecture app)
  if (pathname === '/') {
    return NextResponse.next()
  }

  // Dashboard routes require a session cookie
  if (
    pathname.startsWith('/student/') ||
    pathname.startsWith('/teacher/')
  ) {
    const token = request.cookies.get('session_token')
    if (!token) {
      const url = request.nextUrl.clone()
      url.pathname = '/login'
      return NextResponse.redirect(url)
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/student/:path*', '/teacher/:path*'],
}
