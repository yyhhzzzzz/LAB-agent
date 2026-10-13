<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import axios from 'axios'
import { useRoute, useRouter } from 'vue-router'
import {
  createEquipment,
  listEquipments,
  uploadEquipmentDocument,
  type Equipment,
  type EquipmentCreatePayload,
  type EquipmentStatus
} from '@/api/equipment'
import { createCollege, createLaboratory, createStudent, createTeacher, listColleges, listLaboratories, listStudents, listTeachers, updateUserCollege, type College, type Laboratory, type StudentOption, type TeacherOption } from '@/api/organization'
import { useAuthStore } from '@/stores/auth'
import ManagementSidebar from '@/components/ManagementSidebar.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const equipments = ref<Equipment[]>([])
const colleges = ref<College[]>([])
const laboratories = ref<Laboratory[]>([])
const teachers = ref<TeacherOption[]>([])
const students = ref<StudentOption[]>([])
const isLoading = ref(true)
const activeRequest = ref<'equipment' | 'document' | 'college' | 'laboratory' | 'student' | 'teacher' | 'teacher-college' | 'student-college' | null>(null)
const pageError = ref('')
const successMessage = ref('')
const documentFile = ref<File | null>(null)
const documentInput = ref<HTMLInputElement | null>(null)

const equipmentForm = reactive<EquipmentCreatePayload>({
  equipment_code: '',
  name: '',
  model: '',
  manufacturer: '',
  serial_number: '',
  laboratory_id: '',
  status: 'available',
  description: ''
})

const documentForm = reactive({ equipmentCode: '', title: '' })
const collegeForm = reactive({ name: '' })
const laboratoryForm = reactive({ laboratory_number: '', college_id: '', manager_teacher_id: '' })
const studentForm = reactive({ username: '', display_name: '', password: '', email: '', college_id: '' })
const teacherForm = reactive({ username: '', display_name: '', password: '', email: '', college_id: '' })
const teacherCollegeForm = reactive({ teacher_id: '', college_id: '' })
const studentCollegeForm = reactive({ student_id: '', college_id: '' })

const canManage = computed(() => auth.user?.role === 'teacher' || auth.user?.role === 'admin')
const isAdmin = computed(() => auth.user?.role === 'admin')
const isStudent = computed(() => auth.user?.role === 'student')
const activeModule = computed<'equipment' | 'users' | 'laboratories' | 'student'>(() => {
  if (route.name === 'management-users') return 'users'
  if (route.name === 'management-laboratories') return 'laboratories'
  if (route.name === 'management-equipment') return 'equipment'
  return 'student'
})
const pageTitle = computed(() => ({
  equipment: '设备管理',
  users: '用户管理',
  laboratories: '实验室管理',
  student: '我的实验室'
})[activeModule.value])
const pageDescription = computed(() => ({
  equipment: '维护设备档案与设备知识文档。',
  users: '创建账号、查看用户并维护所属学院。',
  laboratories: '维护学院、实验室和实验室负责人。',
  student: '查看本学院实验室和设备。'
})[activeModule.value])
const visibleLaboratories = computed(() => laboratories.value)
const teachersForSelectedCollege = computed(() => teachers.value.filter((teacher) => teacher.college_id === laboratoryForm.college_id))
const currentTeacherCollegeId = computed(() => teachers.value.find((teacher) => teacher.id === auth.user?.id)?.college_id || '')
const collegeName = (collegeId: string) => colleges.value.find((college) => college.id === collegeId)?.name || '所属学院'
const laboratoryNumber = (laboratoryId: string | null | undefined) => laboratories.value.find((laboratory) => laboratory.id === laboratoryId)?.laboratory_number || '未分配实验室'

const statusLabels: Record<EquipmentStatus, string> = {
  available: '可用',
  in_use: '使用中',
  maintenance: '维修中',
  retired: '已报废'
}
const statusClass = (status: EquipmentStatus) => `status--${status}`

const resetMessages = () => {
  pageError.value = ''
  successMessage.value = ''
}

const errorDetail = (cause: unknown, fallback: string) => {
  if (axios.isAxiosError<{ detail?: string }>(cause)) {
    return cause.response?.data?.detail || `${fallback}${cause.response?.status ? `（HTTP ${cause.response.status}）` : ''}`
  }
  return cause instanceof Error ? cause.message : fallback
}

const loadData = async () => {
  isLoading.value = true
  pageError.value = ''
  try {
    const [equipmentData, laboratoryData, collegeData, teacherData, studentData] = await Promise.all([
      listEquipments(),
      listLaboratories(),
      listColleges(),
      canManage.value ? listTeachers() : Promise.resolve([]),
      canManage.value ? listStudents() : Promise.resolve([])
    ])
    equipments.value = equipmentData
    laboratories.value = laboratoryData
    colleges.value = collegeData
    teachers.value = teacherData
    students.value = studentData
    if (!isAdmin.value && currentTeacherCollegeId.value) studentForm.college_id = currentTeacherCollegeId.value
    if (!laboratoryForm.college_id && collegeData.length) laboratoryForm.college_id = collegeData[0].id
    if (!studentForm.college_id && collegeData.length) studentForm.college_id = collegeData[0].id
    if (!teacherForm.college_id && collegeData.length) teacherForm.college_id = collegeData[0].id
    if (!teacherCollegeForm.teacher_id && teacherData.length) teacherCollegeForm.teacher_id = teacherData[0].id
    if (!studentCollegeForm.student_id && studentData.length) studentCollegeForm.student_id = studentData[0].id
    if (!documentForm.equipmentCode && equipmentData.length) documentForm.equipmentCode = equipmentData[0].equipment_code
  } catch (cause) {
    pageError.value = errorDetail(cause, `无法加载${pageTitle.value}数据。`)
  } finally {
    isLoading.value = false
  }
}

const submitEquipment = async () => {
  if (activeRequest.value) return
  resetMessages()
  activeRequest.value = 'equipment'
  try {
    const created = await createEquipment({
      ...equipmentForm,
      equipment_code: equipmentForm.equipment_code.trim(),
      name: equipmentForm.name.trim(),
      laboratory_id: equipmentForm.laboratory_id
    })
    equipments.value = [created, ...equipments.value]
    documentForm.equipmentCode ||= created.equipment_code
    Object.assign(equipmentForm, {
      equipment_code: '', name: '', model: '', manufacturer: '', serial_number: '', laboratory_id: '', status: 'available', description: ''
    })
    successMessage.value = `设备「${created.name}」已创建。`
  } catch (cause) {
    pageError.value = errorDetail(cause, '设备创建失败，请检查填写内容。')
  } finally {
    activeRequest.value = null
  }
}

const onDocumentSelected = (event: Event) => {
  const input = event.target as HTMLInputElement
  documentFile.value = input.files?.[0] ?? null
}

const submitDocument = async () => {
  if (activeRequest.value || !documentFile.value) return
  resetMessages()
  activeRequest.value = 'document'
  try {
    const result = await uploadEquipmentDocument(documentFile.value, documentForm.equipmentCode, documentForm.title)
    successMessage.value = result.duplicate ? '该设备已存在相同文档，未重复保存。' : `文档「${result.title}」已上传。`
    documentFile.value = null
    documentForm.title = ''
    if (documentInput.value) documentInput.value.value = ''
  } catch (cause) {
    pageError.value = errorDetail(cause, '文档上传失败，请稍后重试。')
  } finally {
    activeRequest.value = null
  }
}

const submitCollege = async () => {
  if (activeRequest.value) return
  resetMessages()
  activeRequest.value = 'college'
  try {
    const college = await createCollege({ name: collegeForm.name.trim() })
    colleges.value = [...colleges.value, college]
    laboratoryForm.college_id ||= college.id
    studentForm.college_id ||= college.id
    collegeForm.name = ''
    successMessage.value = `学院「${college.name}」已创建。`
  } catch (cause) {
    pageError.value = errorDetail(cause, '学院创建失败，请检查名称。')
  } finally {
    activeRequest.value = null
  }
}

const submitLaboratory = async () => {
  if (activeRequest.value) return
  resetMessages()
  activeRequest.value = 'laboratory'
  try {
    const laboratory = await createLaboratory({
      laboratory_number: laboratoryForm.laboratory_number.trim(),
      college_id: laboratoryForm.college_id,
      manager_teacher_id: laboratoryForm.manager_teacher_id.trim()
    })
    laboratories.value = [...laboratories.value, laboratory]
    laboratoryForm.laboratory_number = ''
    laboratoryForm.manager_teacher_id = ''
    successMessage.value = `实验室「${laboratory.laboratory_number}」已创建。`
  } catch (cause) {
    pageError.value = errorDetail(cause, '实验室创建失败，请核对学院和教师。')
  } finally {
    activeRequest.value = null
  }
}

const submitStudent = async () => {
  if (activeRequest.value) return
  resetMessages()
  activeRequest.value = 'student'
  try {
    const created = await createStudent({
      username: studentForm.username.trim(),
      display_name: studentForm.display_name.trim(),
      password: studentForm.password,
      email: studentForm.email.trim() || undefined,
      college_id: isAdmin.value ? studentForm.college_id : currentTeacherCollegeId.value
    })
    if (isAdmin.value) students.value = [...students.value, created]
    Object.assign(studentForm, { username: '', display_name: '', password: '', email: '' })
    successMessage.value = '学生账号已创建。'
  } catch (cause) {
    pageError.value = errorDetail(cause, '学生账号创建失败，请检查信息。')
  } finally {
    activeRequest.value = null
  }
}

const submitTeacher = async () => {
  if (activeRequest.value) return
  resetMessages()
  activeRequest.value = 'teacher'
  try {
    const created = await createTeacher({
      username: teacherForm.username.trim(),
      display_name: teacherForm.display_name.trim(),
      password: teacherForm.password,
      email: teacherForm.email.trim() || undefined,
      college_id: teacherForm.college_id
    })
    teachers.value = [...teachers.value, created]
    teacherCollegeForm.teacher_id = created.id
    laboratoryForm.college_id = teacherForm.college_id
    laboratoryForm.manager_teacher_id = created.id
    Object.assign(teacherForm, { username: '', display_name: '', password: '', email: '' })
    successMessage.value = `教师账号「${created.display_name}」已创建。`
  } catch (cause) {
    pageError.value = errorDetail(cause, '教师账号创建失败，请检查信息。')
  } finally {
    activeRequest.value = null
  }
}

const assignTeacherCollege = async () => {
  if (activeRequest.value || !teacherCollegeForm.teacher_id || !teacherCollegeForm.college_id) return
  resetMessages()
  activeRequest.value = 'teacher-college'
  try {
    await updateUserCollege(teacherCollegeForm.teacher_id, teacherCollegeForm.college_id)
    teachers.value = teachers.value.map((teacher) => teacher.id === teacherCollegeForm.teacher_id
      ? { ...teacher, college_id: teacherCollegeForm.college_id }
      : teacher)
    successMessage.value = '教师所属学院已更新。'
  } catch (cause) {
    pageError.value = errorDetail(cause, '教师所属学院更新失败。')
  } finally {
    activeRequest.value = null
  }
}

const assignStudentCollege = async () => {
  if (activeRequest.value || !studentCollegeForm.student_id || !studentCollegeForm.college_id) return
  resetMessages()
  activeRequest.value = 'student-college'
  try {
    await updateUserCollege(studentCollegeForm.student_id, studentCollegeForm.college_id)
    students.value = students.value.map((student) => student.id === studentCollegeForm.student_id
      ? { ...student, college_id: studentCollegeForm.college_id }
      : student)
    successMessage.value = '学生所属学院已更新。'
  } catch (cause) {
    pageError.value = errorDetail(cause, '学生所属学院更新失败。')
  } finally {
    activeRequest.value = null
  }
}

const logout = async () => {
  auth.logout()
  await router.replace({ name: 'login' })
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <div class="management-shell">
    <ManagementSidebar v-if="!isStudent" />
    <main class="management-main">
      <header class="management-header">
        <div>
          <button v-if="isStudent" class="back-link" type="button" @click="router.push({ name: 'assistant' })">← 返回助手</button>
          <p class="eyebrow">设备管理</p>
          <h1>{{ pageTitle }}</h1>
          <p class="header-copy">{{ pageDescription }}</p>
        </div>
        <div class="header-account">
          <span class="account-avatar" aria-hidden="true">{{ auth.user?.display_name?.slice(0, 1) || '用' }}</span>
          <span class="header-account__copy"><strong>{{ auth.user?.display_name }}</strong><small>{{ isAdmin ? '管理员' : isStudent ? '学生' : '教师' }}</small></span>
          <button class="logout-button" type="button" @click="logout">退出</button>
        </div>
      </header>

      <p v-if="pageError" class="feedback feedback--error" role="alert">{{ pageError }}</p>
      <p v-if="successMessage" class="feedback feedback--success" role="status">{{ successMessage }}</p>
      <div v-if="isLoading" class="loading-state">正在加载{{ pageTitle }}数据…</div>

      <div v-else class="management-grid">
        <section v-if="activeModule === 'laboratories' && isAdmin" class="panel" aria-labelledby="college-form-heading">
          <div class="panel-heading"><div><p class="eyebrow">COLLEGE DIRECTORY</p><h2 id="college-form-heading">添加学院</h2></div><span class="panel-count">{{ colleges.length }} 个</span></div>
          <form class="stack-form" @submit.prevent="submitCollege">
            <label>学院名称<input v-model="collegeForm.name" required maxlength="120" placeholder="如 信息工程学院" /></label>
            <button class="primary-button" type="submit" :disabled="activeRequest !== null || !collegeForm.name.trim()">{{ activeRequest === 'college' ? '保存中…' : '添加学院' }}</button>
          </form>
        </section>

        <section v-if="activeModule === 'users' && isAdmin" class="panel" aria-labelledby="teacher-form-heading">
          <div class="panel-heading"><div><p class="eyebrow">TEACHER ACCOUNTS</p><h2 id="teacher-form-heading">添加教师</h2></div><span class="panel-count">{{ teachers.length }} 位</span></div>
          <form class="form-grid" @submit.prevent="submitTeacher">
            <label>用户名<input v-model="teacherForm.username" required maxlength="64" autocomplete="off" /></label>
            <label>教师姓名<input v-model="teacherForm.display_name" required maxlength="120" /></label>
            <label>初始密码<input v-model="teacherForm.password" type="password" required minlength="8" maxlength="128" autocomplete="new-password" /></label>
            <label>邮箱<input v-model="teacherForm.email" type="email" maxlength="254" /></label>
            <label class="form-grid__wide">所属学院<select v-model="teacherForm.college_id" required><option value="" disabled>选择学院</option><option v-for="college in colleges" :key="college.id" :value="college.id">{{ college.name }}</option></select></label>
            <button class="primary-button form-grid__wide" type="submit" :disabled="activeRequest !== null || !teacherForm.username.trim() || !teacherForm.display_name.trim() || teacherForm.password.length < 8 || !teacherForm.college_id">{{ activeRequest === 'teacher' ? '创建中…' : '创建教师账号' }}</button>
          </form>
          <p v-if="!colleges.length" class="panel-note">请先添加学院，再创建教师账号。</p>
        </section>

        <section v-if="activeModule === 'laboratories' && isAdmin" class="panel" aria-labelledby="laboratory-form-heading">
          <div class="panel-heading"><div><p class="eyebrow">LABORATORY DIRECTORY</p><h2 id="laboratory-form-heading">添加实验室</h2></div><span class="panel-count">{{ laboratories.length }} 间</span></div>
          <form class="stack-form" @submit.prevent="submitLaboratory">
            <label>所属学院<select v-model="laboratoryForm.college_id" required @change="laboratoryForm.manager_teacher_id = ''"><option value="" disabled>选择学院</option><option v-for="college in colleges" :key="college.id" :value="college.id">{{ college.name }}</option></select></label>
            <label>实验室号码<input v-model="laboratoryForm.laboratory_number" required maxlength="64" placeholder="如 A-201" /></label>
            <label>管理教师<select v-model="laboratoryForm.manager_teacher_id" required><option value="" disabled>选择本学院教师</option><option v-for="teacher in teachersForSelectedCollege" :key="teacher.id" :value="teacher.id">{{ teacher.display_name }} · {{ teacher.username }}</option></select></label>
            <button class="primary-button" type="submit" :disabled="activeRequest !== null || !laboratoryForm.college_id || !laboratoryForm.manager_teacher_id || !laboratoryForm.laboratory_number.trim()">{{ activeRequest === 'laboratory' ? '保存中…' : '添加实验室' }}</button>
          </form>
          <p class="panel-note">实验室号码在同一学院内不能重复。</p>
        </section>

        <section v-if="activeModule === 'users' && isAdmin" class="panel" aria-labelledby="teacher-college-heading">
          <div class="panel-heading"><div><p class="eyebrow">TEACHER DIRECTORY</p><h2 id="teacher-college-heading">绑定教师学院</h2></div></div>
          <form class="stack-form" @submit.prevent="assignTeacherCollege">
            <label>教师<select v-model="teacherCollegeForm.teacher_id" required><option value="" disabled>选择教师</option><option v-for="teacher in teachers" :key="teacher.id" :value="teacher.id">{{ teacher.display_name }} · {{ teacher.username }}</option></select></label>
            <label>所属学院<select v-model="teacherCollegeForm.college_id" required><option value="" disabled>选择学院</option><option v-for="college in colleges" :key="college.id" :value="college.id">{{ college.name }}</option></select></label>
            <button class="secondary-button" type="submit" :disabled="activeRequest !== null || !teacherCollegeForm.teacher_id || !teacherCollegeForm.college_id">{{ activeRequest === 'teacher-college' ? '更新中…' : '绑定学院' }}</button>
          </form>
        </section>

        <section v-if="activeModule === 'users' && canManage" class="panel" aria-labelledby="student-form-heading">
          <div class="panel-heading"><div><p class="eyebrow">STUDENT ACCOUNTS</p><h2 id="student-form-heading">添加学生</h2></div></div>
          <form class="form-grid" @submit.prevent="submitStudent">
            <label>用户名<input v-model="studentForm.username" required maxlength="64" autocomplete="off" /></label>
            <label>学生姓名<input v-model="studentForm.display_name" required maxlength="120" /></label>
            <label>初始密码<input v-model="studentForm.password" type="password" required minlength="8" maxlength="128" autocomplete="new-password" /></label>
            <label>邮箱<input v-model="studentForm.email" type="email" maxlength="254" /></label>
            <label v-if="isAdmin" class="form-grid__wide">所属学院<select v-model="studentForm.college_id" required><option value="" disabled>选择学院</option><option v-for="college in colleges" :key="college.id" :value="college.id">{{ college.name }}</option></select></label>
            <p v-else class="field-hint form-grid__wide">{{ currentTeacherCollegeId ? '学生将关联到你的所属学院。' : '请先联系管理员为你的教师账号分配学院。' }}</p>
            <button class="primary-button form-grid__wide" type="submit" :disabled="activeRequest !== null || !studentForm.username.trim() || !studentForm.display_name.trim() || studentForm.password.length < 8 || (isAdmin && !studentForm.college_id) || (!isAdmin && !currentTeacherCollegeId)">{{ activeRequest === 'student' ? '创建中…' : '创建学生账号' }}</button>
          </form>
        </section>

        <section v-if="activeModule === 'users' && isAdmin" class="panel" aria-labelledby="student-college-heading">
          <div class="panel-heading"><div><p class="eyebrow">STUDENT DIRECTORY</p><h2 id="student-college-heading">绑定学生学院</h2></div></div>
          <form class="stack-form" @submit.prevent="assignStudentCollege">
            <label>学生<select v-model="studentCollegeForm.student_id" required><option value="" disabled>选择学生</option><option v-for="student in students" :key="student.id" :value="student.id">{{ student.display_name }} · {{ student.username }}{{ student.college_id ? `（${collegeName(student.college_id)}）` : '（尚未分配学院）' }}</option></select></label>
            <label>所属学院<select v-model="studentCollegeForm.college_id" required><option value="" disabled>选择学院</option><option v-for="college in colleges" :key="college.id" :value="college.id">{{ college.name }}</option></select></label>
            <button class="secondary-button" type="submit" :disabled="activeRequest !== null || !studentCollegeForm.student_id || !studentCollegeForm.college_id">{{ activeRequest === 'student-college' ? '更新中…' : '绑定学院' }}</button>
          </form>
        </section>

        <section v-if="activeModule === 'users' && canManage" class="panel panel--list" aria-labelledby="teacher-list-heading">
          <div class="panel-heading"><div><p class="eyebrow">TEACHER DIRECTORY</p><h2 id="teacher-list-heading">教师账号</h2></div><span class="panel-count">{{ teachers.length }} 位</span></div>
          <div v-if="teachers.length" class="table-wrap"><table><thead><tr><th>姓名</th><th>用户名</th><th>所属学院</th></tr></thead><tbody><tr v-for="teacher in teachers" :key="teacher.id"><td><strong>{{ teacher.display_name }}</strong></td><td class="mono">{{ teacher.username }}</td><td>{{ teacher.college_name || collegeName(teacher.college_id || '') }}</td></tr></tbody></table></div>
          <p v-else class="empty-state">暂无教师账号。</p>
        </section>

        <section v-if="activeModule === 'users' && canManage" class="panel panel--list" aria-labelledby="student-list-heading">
          <div class="panel-heading"><div><p class="eyebrow">STUDENT DIRECTORY</p><h2 id="student-list-heading">学生账号</h2></div><span class="panel-count">{{ students.length }} 位</span></div>
          <div v-if="students.length" class="table-wrap"><table><thead><tr><th>姓名</th><th>用户名</th><th>所属学院</th></tr></thead><tbody><tr v-for="student in students" :key="student.id"><td><strong>{{ student.display_name }}</strong></td><td class="mono">{{ student.username }}</td><td>{{ collegeName(student.college_id || '') }}</td></tr></tbody></table></div>
          <p v-else class="empty-state">暂无学生账号。</p>
        </section>

        <section v-if="activeModule === 'equipment' && canManage" class="panel panel--equipment" aria-labelledby="equipment-form-heading">
          <div class="panel-heading"><div><p class="eyebrow">EQUIPMENT REGISTER</p><h2 id="equipment-form-heading">添加设备</h2></div><span class="panel-count">{{ equipments.length }} 台</span></div>
          <form class="form-grid" @submit.prevent="submitEquipment">
            <label>设备编码<input v-model="equipmentForm.equipment_code" required maxlength="64" placeholder="如 CENT-01" /></label>
            <label>设备名称<input v-model="equipmentForm.name" required maxlength="160" placeholder="如 台式离心机" /></label>
            <label>型号<input v-model="equipmentForm.model" maxlength="120" placeholder="型号（可选）" /></label>
            <label>制造商<input v-model="equipmentForm.manufacturer" maxlength="160" placeholder="制造商（可选）" /></label>
            <label>序列号<input v-model="equipmentForm.serial_number" maxlength="120" placeholder="序列号（可选）" /></label>
            <label>所属实验室<select v-model="equipmentForm.laboratory_id" required><option value="" disabled>选择实验室</option><option v-for="laboratory in visibleLaboratories" :key="laboratory.id" :value="laboratory.id">{{ collegeName(laboratory.college_id) }} · {{ laboratory.laboratory_number }}</option></select></label>
            <label>初始状态<select v-model="equipmentForm.status"><option v-for="(label, value) in statusLabels" :key="value" :value="value">{{ label }}</option></select></label>
            <label class="form-grid__wide">描述<textarea v-model="equipmentForm.description" rows="3" placeholder="补充设备用途、注意事项等" /></label>
            <button class="primary-button form-grid__wide" type="submit" :disabled="activeRequest !== null || !equipmentForm.equipment_code.trim() || !equipmentForm.name.trim() || !equipmentForm.laboratory_id">{{ activeRequest === 'equipment' ? '保存中…' : '添加设备' }}</button>
          </form>
        </section>

        <section v-if="activeModule === 'equipment' && canManage" class="panel" aria-labelledby="document-form-heading">
          <div class="panel-heading"><div><p class="eyebrow">KNOWLEDGE FILES</p><h2 id="document-form-heading">上传设备文档</h2></div></div>
          <form class="stack-form" @submit.prevent="submitDocument">
            <label>关联设备<select v-model="documentForm.equipmentCode" required><option value="" disabled>选择设备</option><option v-for="equipment in equipments" :key="equipment.id" :value="equipment.equipment_code">{{ equipment.equipment_code }} · {{ equipment.name }}</option></select></label>
            <label>文档标题<input v-model="documentForm.title" maxlength="255" placeholder="默认使用文件名" /></label>
            <label class="file-picker">文档文件<input ref="documentInput" type="file" accept=".pdf,.md,.txt,text/plain,application/pdf" required @change="onDocumentSelected" /><span>{{ documentFile?.name || '选择 PDF、Markdown 或 TXT 文件' }}</span></label>
            <button class="secondary-button" type="submit" :disabled="activeRequest !== null || !documentFile || !documentForm.equipmentCode">{{ activeRequest === 'document' ? '上传中…' : '上传文档' }}</button>
          </form>
          <p class="panel-note">文档会归档到选定设备，并进入知识库处理流程。</p>
        </section>

        <section v-if="activeModule === 'laboratories' || activeModule === 'student'" class="panel panel--list" aria-labelledby="laboratory-list-heading">
          <div class="panel-heading"><div><p class="eyebrow">YOUR LABORATORIES</p><h2 id="laboratory-list-heading">{{ isStudent ? '本学院可用实验室' : isAdmin ? '全部实验室' : '我管理的实验室' }}</h2></div></div>
          <div v-if="visibleLaboratories.length" class="table-wrap"><table><thead><tr><th>实验室号码</th><th>学院</th><th v-if="isAdmin">管理教师</th></tr></thead><tbody><tr v-for="laboratory in visibleLaboratories" :key="laboratory.id"><td class="mono">{{ laboratory.laboratory_number }}</td><td>{{ collegeName(laboratory.college_id) }}</td><td v-if="isAdmin">{{ laboratory.manager_name || laboratory.manager_teacher_id }}</td></tr></tbody></table></div>
          <p v-else class="empty-state">{{ isStudent ? '所属学院暂时没有可用实验室。' : '暂无实验室。' }}</p>
        </section>

        <section v-if="activeModule === 'equipment' || activeModule === 'student'" class="panel panel--list" aria-labelledby="equipment-list-heading">
          <div class="panel-heading"><div><p class="eyebrow">REGISTERED ASSETS</p><h2 id="equipment-list-heading">设备档案</h2></div></div>
          <div v-if="equipments.length" class="table-wrap"><table><thead><tr><th>编码</th><th>名称</th><th>所属实验室</th><th>状态</th></tr></thead><tbody><tr v-for="equipment in equipments" :key="equipment.id"><td class="mono">{{ equipment.equipment_code }}</td><td><strong>{{ equipment.name }}</strong><small>{{ equipment.model || '未填写型号' }}</small></td><td>{{ laboratoryNumber(equipment.laboratory_id) }}</td><td><span class="status" :class="statusClass(equipment.status)">{{ statusLabels[equipment.status] }}</span></td></tr></tbody></table></div>
          <p v-else class="empty-state">{{ isStudent ? '本学院实验室暂时没有设备。' : '还没有设备，请先添加一台设备。' }}</p>
        </section>

      </div>
    </main>
  </div>
</template>

<style scoped>
.management-shell { display: flex; min-height: 100dvh; background: var(--c-bg-0); }
.management-main { flex: 1; min-width: 0; width: min(1260px, calc(100% - 48px)); max-width: 1260px; margin: 0 auto; padding: 32px 24px 56px; }
.management-header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-start; gap: 24px; padding-bottom: 24px; border-bottom: 1px solid var(--c-line-1); }
.back-link { margin-bottom: 24px; color: var(--c-accent); font-size: var(--fs-sm); }
.back-link:hover { text-decoration: underline; }
.eyebrow { color: var(--c-accent); font-size: 10px; font-weight: var(--fw-semibold); letter-spacing: .15em; }
h1 { margin-top: 10px; font-size: 30px; letter-spacing: -.035em; }
.header-copy { margin-top: 8px; color: var(--c-fg-1); }
.header-account { display: flex; align-items: center; gap: 9px; flex: 0 0 auto; min-width: max-content; margin-left: auto; padding-top: 9px; color: var(--c-fg-0); }
.account-avatar { display: grid; width: 31px; height: 31px; flex: 0 0 31px; place-items: center; border-radius: 50%; color: var(--c-accent); background: var(--c-accent-soft); font-size: 12px; font-weight: 600; }
.header-account__copy { display: grid; gap: 1px; }.header-account strong { font-size: 12px; }.header-account small { color: var(--c-fg-2); font-size: 10px; }
.logout-button { min-width: 38px; flex: 0 0 auto; padding: 5px 7px; color: var(--c-fg-1); border-radius: var(--r-sm); font-size: 11px; white-space: nowrap; }
.logout-button:hover { color: var(--c-bad); background: var(--c-danger-soft); }
.feedback { padding: 10px 12px; margin-top: 18px; border-left: 2px solid; font-size: var(--fs-sm); }.feedback--error { color: var(--c-bad); background: var(--c-danger-soft); border-color: var(--c-bad); }.feedback--success { color: var(--c-ok); background: var(--c-success-soft); border-color: var(--c-ok); }
.loading-state { padding: 56px 0; color: var(--c-fg-1); text-align: center; }
.management-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin-top: 24px; }
.panel { min-width: 0; padding: 22px; background: var(--c-bg-1); border: 1px solid var(--c-line-1); border-radius: var(--r-md); }.panel--equipment { grid-row: span 2; }.panel--list { min-height: 230px; }
.panel-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 20px; }.panel-heading h2 { margin-top: 7px; font-size: 17px; }.panel-count { padding-top: 2px; color: var(--c-fg-2); font: 11px var(--ff-mono); }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 12px; }.form-grid__wide { grid-column: 1 / -1; }.stack-form { display: grid; gap: 14px; }
label { display: grid; gap: 6px; color: var(--c-fg-1); font-size: var(--fs-sm); font-weight: var(--fw-medium); }
input, select, textarea { width: 100%; padding: 9px 10px; color: var(--c-fg-0); background: var(--c-bg-1); border: 1px solid var(--c-line-2); border-radius: var(--r-sm); outline: 0; font-size: var(--fs-sm); transition: border-color var(--dur-fast), box-shadow var(--dur-fast); }
textarea { resize: vertical; line-height: 1.5; } input:focus, select:focus, textarea:focus { border-color: var(--c-accent); box-shadow: 0 0 0 3px var(--c-accent-soft); } input::placeholder, textarea::placeholder { color: var(--c-fg-3); }
.primary-button, .secondary-button { min-height: 38px; padding: 0 14px; border-radius: var(--r-sm); font-size: var(--fs-sm); font-weight: var(--fw-semibold); transition: background var(--dur-fast), opacity var(--dur-fast); }.primary-button { color: var(--c-accent-fg); background: var(--c-accent); }.primary-button:hover:not(:disabled) { background: var(--c-accent-3); }.secondary-button { color: var(--c-accent); border: 1px solid var(--c-accent-line); background: var(--c-accent-soft); }.secondary-button:hover:not(:disabled) { background: rgba(15, 118, 110, .15); }.primary-button:disabled, .secondary-button:disabled { cursor: not-allowed; opacity: .5; }
.file-picker input { position: absolute; width: 1px; height: 1px; opacity: 0; }.file-picker span { display: block; padding: 11px 10px; overflow: hidden; color: var(--c-fg-1); border: 1px dashed var(--c-line-2); border-radius: var(--r-sm); text-overflow: ellipsis; white-space: nowrap; }.file-picker:hover span { border-color: var(--c-accent); color: var(--c-accent); }
.panel-note, .field-hint { color: var(--c-fg-2); font-size: var(--fs-xs); line-height: 1.5; }.panel-note { margin-top: 15px; }.field-hint { margin-top: -7px; }
.table-wrap { overflow-x: auto; } table { width: 100%; border-collapse: collapse; font-size: var(--fs-sm); } th { padding: 0 10px 10px; color: var(--c-fg-2); font-size: var(--fs-xs); font-weight: var(--fw-medium); text-align: left; white-space: nowrap; } td { padding: 12px 10px; border-top: 1px solid var(--c-line-1); color: var(--c-fg-1); white-space: nowrap; } td:first-child, th:first-child { padding-left: 0; } td:last-child, th:last-child { padding-right: 0; } td strong, td small { display: block; } td strong { color: var(--c-fg-0); font-weight: var(--fw-medium); } td small { margin-top: 3px; color: var(--c-fg-2); font-size: var(--fs-xs); }
.status { display: inline-flex; padding: 3px 6px; border-radius: var(--r-xs); font-size: var(--fs-xs); }.status--available { color: var(--c-ok); background: var(--c-success-soft); }.status--in_use { color: var(--c-accent); background: var(--c-accent-soft); }.status--maintenance { color: var(--c-warn); background: var(--c-warning-soft); }.status--retired { color: var(--c-fg-1); background: var(--c-neutral-soft); }
.empty-state { padding: 24px 0 8px; color: var(--c-fg-2); font-size: var(--fs-sm); }
@media (max-width: 900px) { .management-main { width: min(100% - 40px, 680px); padding: 24px 20px 56px; }.management-grid { grid-template-columns: 1fr; }.panel--equipment { grid-row: auto; } }
@media (max-width: 760px) { .management-shell { display: block; }.management-main { width: min(100% - 32px, 680px); } }
@media (max-width: 540px) { .management-main { width: calc(100% - 32px); padding: 24px 16px 32px; }.management-header { display: block; }.header-account { margin-top: 20px; }.form-grid { grid-template-columns: 1fr; }.form-grid__wide { grid-column: auto; }.panel { padding: 17px; } }
</style>
