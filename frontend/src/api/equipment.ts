import { apiClient } from '@/api/client'

export type EquipmentStatus = 'available' | 'in_use' | 'maintenance' | 'retired'
export type WorkOrderPriority = 'low' | 'normal' | 'high' | 'urgent'

export interface Equipment {
  id: string
  equipment_code: string
  name: string
  model: string | null
  manufacturer: string | null
  serial_number: string | null
  status: EquipmentStatus
  description: string | null
  laboratory_id: string | null
  laboratory_number?: string | null
  college_id?: string | null
  created_at: string
}

export interface EquipmentCreatePayload {
  equipment_code: string
  name: string
  model?: string
  manufacturer?: string
  serial_number?: string
  status?: EquipmentStatus
  description?: string
  laboratory_id: string
}

export interface WorkOrder {
  id: string
  equipment_id: string
  equipment_code: string
  equipment_name: string
  requester_id: string
  requester_name: string
  title: string
  description: string
  priority: WorkOrderPriority
  status: string
  resolution?: string | null
  assignee_id?: string | null
  created_at: string
}

export interface WorkOrderCreatePayload {
  equipment_id: string
  title: string
  description: string
  priority: WorkOrderPriority
}

export interface WorkOrderUpdatePayload {
  status: string
  resolution?: string
  assignee_id?: string
}

export interface DocumentUploadResponse {
  id: string
  filename: string
  title: string
  equipment_code: string | null
  status: string
  chunk_count: number
  duplicate: boolean
}

export async function listEquipments(): Promise<Equipment[]> {
  const { data } = await apiClient.get<Equipment[]>('/api/v1/equipments')
  return data
}

export async function createEquipment(payload: EquipmentCreatePayload): Promise<Equipment> {
  const { data } = await apiClient.post<Equipment>('/api/v1/equipments', payload)
  return data
}

export async function listWorkOrders(): Promise<WorkOrder[]> {
  const { data } = await apiClient.get<WorkOrder[]>('/api/v1/work-orders')
  return data
}

export async function createWorkOrder(payload: WorkOrderCreatePayload): Promise<WorkOrder> {
  const { data } = await apiClient.post<WorkOrder>('/api/v1/work-orders', payload)
  return data
}

export async function updateWorkOrder(id: string, payload: WorkOrderUpdatePayload): Promise<WorkOrder> {
  const { data } = await apiClient.patch<WorkOrder>(`/api/v1/work-orders/${id}/status`, payload)
  return data
}

export async function uploadEquipmentDocument(
  file: File,
  equipmentCode: string,
  title?: string
): Promise<DocumentUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('equipment_code', equipmentCode)
  if (title?.trim()) formData.append('title', title.trim())

  const { data } = await apiClient.post<DocumentUploadResponse>('/api/v1/documents', formData)
  return data
}
