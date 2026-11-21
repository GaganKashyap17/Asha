import { Settings, User, Building, MapPin, Globe, Shield, Bell } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'

export default function SettingsPage() {
  const { user } = useAuth()

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Settings className="w-7 h-7 text-green-600" /> Settings
        </h2>
      </div>

      {/* Worker Profile */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 space-y-4">
        <div className="flex items-center gap-3 pb-3 border-b border-gray-100">
          <div className="w-10 h-10 rounded-xl bg-green-100 text-green-700 flex items-center justify-center">
            <User className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-gray-900">Worker Profile</h3>
            <p className="text-xs text-gray-500">Your registered ASHA healthcare worker identity</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          {[
            ['Worker ID', user?.worker_id, Shield],
            ['Full Name', user?.name, User],
            ['District', user?.district, MapPin],
            ['Assigned PHC', user?.phc, Building],
            ['Primary Language', user?.language || 'Tamil / English', Globe],
            ['Role', user?.role || 'ASHA Worker', Shield],
          ].map(([k, v, Icon]: any) => (
            <div key={k} className="bg-gray-50/80 rounded-xl p-3.5 border border-gray-100">
              <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-1">
                <Icon className="w-3.5 h-3.5 text-green-600" />
                <span>{k}</span>
              </div>
              <p className="font-semibold text-gray-900">{v || '—'}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Application Preferences */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 space-y-4">
        <div className="flex items-center gap-3 pb-3 border-b border-gray-100">
          <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center">
            <Bell className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-gray-900">Application Preferences</h3>
            <p className="text-xs text-gray-500">Configure your local clinical preferences</p>
          </div>
        </div>

        <div className="space-y-3 text-sm">
          <div className="flex items-center justify-between p-3.5 bg-gray-50/70 rounded-xl border border-gray-100">
            <div>
              <p className="font-semibold text-gray-800">Voice Language</p>
              <p className="text-xs text-gray-500">Default spoken language for speech interactions</p>
            </div>
            <span className="font-semibold text-xs px-3 py-1 bg-green-100 text-green-800 rounded-lg">
              {user?.language || 'Tamil'}
            </span>
          </div>

          <div className="flex items-center justify-between p-3.5 bg-gray-50/70 rounded-xl border border-gray-100">
            <div>
              <p className="font-semibold text-gray-800">Clinical Guidelines Standard</p>
              <p className="text-xs text-gray-500">High-risk danger detection protocol</p>
            </div>
            <span className="font-semibold text-xs px-3 py-1 bg-blue-100 text-blue-800 rounded-lg">
              WHO / IMNCI
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
